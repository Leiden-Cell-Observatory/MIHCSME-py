"""Audit a MIHCSME metadata file before it is shared or uploaded to OMERO.

Goes beyond the Pydantic validation in mihcsme_py: checks plate geometry,
duplicate wells, units embedded in values, inconsistent spellings, ORCID
checksums, NCBITaxon / ontology-label use and completeness of recommended
fields. With --online it also resolves every "<Column> Term Accession" value
against OLS4 / Cellosaurus.

Usage (from the repo root):
    uv run python .claude/skills/mihcsme-metadata/scripts/audit_metadata.py FILE \
        --plate-format 384 [--online]

FILE is a MIHCSME .xlsx or a .json dump of MIHCSMEMetadata.
Exit code: 0 = no errors (warnings allowed), 1 = errors found.
"""

from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from mihcsme_py import MIHCSMEMetadata, parse_excel_to_model

DIMS = {"96": (8, 12), "384": (16, 24), "1536": (32, 48)}
UNIT_IN_VALUE = re.compile(r"^\s*[-+]?\d*\.?\d+\s*(%|[a-zA-Zµμ]+)\s*$")
NUMERIC = re.compile(r"^\s*[-+]?\d*\.?\d+(e[-+]?\d+)?\s*$", re.I)
CURIE = re.compile(r"^[A-Za-z][A-Za-z0-9_.]*:[A-Za-z0-9_.-]+$")
TAXON = re.compile(r"^NCBITaxon:\d+$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NUMERIC_COL_HINTS = ("dose", "conc", "concentration", "time", "repl", "repid", "replid", "passage")
UNIT_COL_HINTS = ("unit",)

RECOMMENDED = {
    "InvestigationInformation": {
        "DataOwner": [
            "First Name",
            "Last Name",
            "E-Mail Address",
            "ORCID investigator",
            "Institute",
        ],
        "InvestigationInfo": ["Investigation Title", "Investigation description"],
    },
    "StudyInformation": {
        "Study": ["Study Title", "Study Description", "Study Key Words"],
        "Biosample": ["Biosample Taxon", "Biosample Organism", "Biosample description"],
        "Protocols": ["growth protocol", "treatment protocol"],
        "Plate": ["Plate type", "Plate type Manufacturer", "Plate type Catalog number"],
    },
    "AssayInformation": {
        "Assay": [
            "Assay Title",
            "Assay Description",
            "Assay Technology Type",
            "Assay Type",
            "Assay number of biological replicates",
            "Number of plates",
        ],
        "AssayComponent": ["Imaging protocol", "Sample preparation protocol"],
        "ImageData": [
            "Image number of pixelsX",
            "Image number of pixelsY",
            "Image number of  z-stacks",
            "Image number of channels",
            "Image number of timepoints",
            "Image sites per well",
        ],
        "ImageAcquisition": ["Microscope id"],
    },
}
# Header fields whose value should be an exact label from a template reference sheet.
ONTOLOGY_LABEL_FIELDS = {
    ("AssayInformation", "Assay", "Assay Technology Type"): "_fbbiImagingMethods",
    ("AssayInformation", "Assay", "Assay Type"): "_efo_assaytypes",
}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def load(path: Path) -> MIHCSMEMetadata:
    if path.suffix.lower() == ".json":
        return MIHCSMEMetadata.model_validate_json(path.read_text())
    return parse_excel_to_model(path)


def orcid_ok(url: str) -> bool:
    digits = url.rsplit("/", 1)[-1].replace("-", "")
    if not re.fullmatch(r"\d{15}[\dX]", digits):
        return False
    total = 0
    for ch in digits[:-1]:
        total = (total + int(ch)) * 2
    check = (12 - total % 11) % 11
    return digits[-1] == ("X" if check == 10 else str(check))


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9µμ%]", "", s.lower()).replace("μ", "µ")


def check_conditions(md: MIHCSMEMetadata, fmt: str | None, rep: Report) -> None:
    if not md.assay_conditions:
        rep.warn("No AssayConditions (well-level metadata) present.")
        return
    seen: dict[tuple[str, str], int] = {}
    columns: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    all_cols = set()
    for c in md.assay_conditions:
        all_cols.update(c.conditions)
    for c in md.assay_conditions:
        key = (c.plate, c.well)
        seen[key] = seen.get(key, 0) + 1
        if fmt:
            rows, cols = DIMS[fmt]
            r = ord(c.well[0]) - ord("A") + 1
            col = int(c.well[1:])
            if r > rows or col > cols:
                rep.error(f"{c.plate}/{c.well}: outside a {fmt}-well plate ({rows}x{cols}).")
        for col_name in all_cols:
            v = c.conditions.get(col_name)
            columns[col_name][str(v).strip() if v not in (None, "") else ""].append(
                f"{c.plate}/{c.well}"
            )
    for (plate, well), n in seen.items():
        if n > 1:
            rep.error(f"{plate}/{well}: appears {n} times in AssayConditions.")

    for col_name, by_value in columns.items():
        low = col_name.lower()
        values = [v for v in by_value if v]
        free_text = any(h in low for h in ("remark", "comment", "note"))
        if "" in by_value and values and not free_text:
            wells = by_value[""]
            rep.warn(
                f"Column '{col_name}': empty in {len(wells)} well(s) ({', '.join(wells[:6])}"
                f"{', ...' if len(wells) > 6 else ''}). Confirm intended (e.g. untreated) or fill."
            )
        if not col_name.endswith("Term Accession") and re.search(
            r"(cid|chebi|pubchem|cellosaurus|cvcl|hgnc|ensembl|uniprot|accession|ontology|\bid\b)",
            low,
        ):
            rep.warn(
                f"Column '{col_name}' looks like an identifier column; name it '<Column> Term Accession' "
                f"with CURIE values so it is resolved and checked."
            )
        if col_name.endswith("Term Accession"):
            for v in values:
                if not CURIE.match(v):
                    rep.error(f"Column '{col_name}': '{v}' is not a CURIE (prefix:id).")
            continue
        if any(h in low for h in NUMERIC_COL_HINTS) and not any(h in low for h in UNIT_COL_HINTS):
            for v in values:
                if UNIT_IN_VALUE.match(v):
                    rep.error(
                        f"Column '{col_name}': value '{v}' embeds a unit; split number and unit "
                        f"into separate columns ({', '.join(by_value[v][:4])})."
                    )
                elif not NUMERIC.match(v):
                    rep.warn(
                        f"Column '{col_name}': non-numeric value '{v}' ({', '.join(by_value[v][:4])})."
                    )
        if any(h in low for h in UNIT_COL_HINTS):
            for v in values:
                if v.lower() in {"um", "ul", "ug"}:
                    rep.warn(
                        f"Column '{col_name}': '{v}' uses 'u' for micro; use the UO label "
                        f"(e.g. 'micromolar') or 'µM' consistently."
                    )
            if len(values) > 1:
                rep.warn(
                    f"Column '{col_name}': mixed units {sorted(values)}. Verify each is real, "
                    f"not a typo or a conversion that was skipped."
                )
        groups: dict[str, list[str]] = defaultdict(list)
        for v in values:
            groups[_norm(v)].append(v)
        for variants in groups.values():
            if len(variants) > 1:
                rep.warn(
                    f"Column '{col_name}': spelling variants of one value {variants}; harmonise."
                )
        if not NUMERIC_ONLY(values) and not col_name.endswith("Term Accession"):
            keys = sorted(groups)
            for i, a in enumerate(keys):
                for b in keys[i + 1 :]:
                    if len(a) >= 4 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8:
                        rep.warn(
                            f"Column '{col_name}': '{groups[a][0]}' and '{groups[b][0]}' are near-identical; "
                            f"typo or two different things?"
                        )

    # A Term Accession column must be filled wherever its base column is.
    for col_name in all_cols:
        acc = f"{col_name} Term Accession"
        if acc in all_cols:
            gaps = [
                f"{c.plate}/{c.well}"
                for c in md.assay_conditions
                if c.conditions.get(col_name) not in (None, "")
                and c.conditions.get(acc) in (None, "")
            ]
            if gaps:
                rep.warn(
                    f"'{acc}' missing for {len(gaps)} well(s) with a '{col_name}' value "
                    f"({', '.join(gaps[:6])}{', ...' if len(gaps) > 6 else ''}); resolve or list as unresolved."
                )

    # Drag-fill: a dose/concentration that changes in (almost) every consecutive well along a row.
    for col_name in all_cols:
        low = col_name.lower()
        if not any(h in low for h in ("dose", "conc")) or col_name.endswith("Term Accession"):
            continue
        by_row: dict[tuple[str, str], list[tuple[int, float]]] = defaultdict(list)
        for c in md.assay_conditions:
            v = c.conditions.get(col_name)
            if v not in (None, "") and NUMERIC.match(str(v)):
                by_row[(c.plate, c.well[0])].append((int(c.well[1:]), float(v)))
        for (plate, row), pts in sorted(by_row.items()):
            pts.sort()
            vals = [v for _, v in pts]
            if len(vals) >= 6 and all(b > a for a, b in zip(vals, vals[1:])):
                rep.warn(
                    f"Column '{col_name}': plate {plate} row {row} increases in every well "
                    f"({vals[0]:g} … {vals[-1]:g}); real dilution series or an Excel drag-fill?"
                )


PLACEHOLDER = re.compile(
    r"^(1337|1234|test|xxx+|abc( def)?|tbd|todo|n/?a|-|\?+|0000-0000-0000-0000)$|^test@|example\.(com|org)",
    re.I,
)


def NUMERIC_ONLY(values: list[str]) -> bool:
    return bool(values) and all(NUMERIC.match(v) for v in values)


def template_labels() -> dict[str, set[str]]:
    """Ontology labels from the bundled template's '_' sheets, read directly.

    (mihcsme_py's parser treats the first term row of these sheets as a header and drops it.)
    """
    import openpyxl

    import mihcsme_py

    path = Path(mihcsme_py.__file__).parent / "templates" / "LEI-MIHCSME.xlsx"
    wb = openpyxl.load_workbook(path, read_only=True)
    out: dict[str, set[str]] = {}
    for ws in wb.worksheets:
        if ws.title.startswith("_"):
            out[ws.title] = {
                str(r[0]).strip().lower()
                for r in ws.iter_rows(values_only=True)
                if r and r[0] is not None and not str(r[0]).startswith("#")
            }
    wb.close()
    return out


def check_header(md: MIHCSMEMetadata, rep: Report) -> None:
    d = md.to_omero_dict()
    for sheet in ("InvestigationInformation", "StudyInformation", "AssayInformation"):
        for group, kv in d.get(sheet, {}).items():
            for k, v in kv.items():
                sv = str(v).strip()
                last = sv.rstrip("/").rsplit("/", 1)[-1]
                if PLACEHOLDER.search(sv) or PLACEHOLDER.search(last):
                    if not (k == "Channel Transmission id" and sv.upper() == "NA"):
                        rep.warn(
                            f"{sheet}/{group} '{k}' = '{sv}' looks like a placeholder; confirm or clear."
                        )
                m = re.match(r"^https?://([^/]+)", sv)
                if m and "." not in m.group(1):
                    rep.warn(f"{sheet}/{group} '{k}' = '{sv}' is not a resolvable URL.")
    refs = template_labels()
    for r in md.reference_sheets:
        refs.setdefault(r.name, set()).update(str(k).strip().lower() for k in r.data)
    for sheet, groups in RECOMMENDED.items():
        for group, keys in groups.items():
            present = d.get(sheet, {}).get(group, {})
            missing = [k for k in keys if not present.get(k)]
            if missing:
                rep.warn(f"{sheet}/{group}: recommended field(s) empty: {', '.join(missing)}")
    owner = d.get("InvestigationInformation", {}).get("DataOwner", {})
    orcids = [owner.get("ORCID investigator")] + list(
        d.get("InvestigationInformation", {}).get("DataCollaborator", {}).values()
    )
    for o in filter(None, orcids):
        if not orcid_ok(o):
            rep.error(f"ORCID '{o}' fails the ISO 7064 checksum or format.")
    email = owner.get("E-Mail Address")
    if email and not EMAIL.match(email):
        rep.error(f"E-Mail Address '{email}' is malformed.")
    taxon = d.get("StudyInformation", {}).get("Biosample", {}).get("Biosample Taxon")
    if taxon and not TAXON.match(taxon):
        rep.error(f"Biosample Taxon '{taxon}' must be a CURIE like 'NCBITaxon:9606'.")
    for (sheet, group, key), ref in ONTOLOGY_LABEL_FIELDS.items():
        v = d.get(sheet, {}).get(group, {}).get(key)
        if v and ref in refs and v.strip().lower() not in refs[ref]:
            rep.warn(f"{key} '{v}' is not an exact label from {ref}; use the ontology label.")
    spec = md.assay_information.specimen if md.assay_information else None
    vis = refs.get("_fbbiVisualizationMethods")
    if spec and vis:
        for i, ch in enumerate(spec.channels, 1):
            if ch.visualization_method and ch.visualization_method.strip().lower() not in vis:
                rep.warn(
                    f"Channel {i} visualization method '{ch.visualization_method}' is not an exact "
                    f"FBbi label; look it up (lookup_term.py search fbbi ...)."
                )
    img = d.get("AssayInformation", {}).get("ImageData", {})
    for k, v in img.items():
        if v and not NUMERIC.match(str(v)):
            rep.error(f"ImageData '{k}' = '{v}' must be a number.")
    n_ch = img.get("Image number of channels")
    if spec and n_ch and NUMERIC.match(n_ch):
        described = len(spec.channels) + (
            1 if spec.channel_transmission_id not in (None, "", "NA") else 0
        )
        if described != int(float(n_ch)):
            rep.warn(
                f"Image number of channels = {n_ch} but {described} channel(s) described in Specimen."
            )
    n_plates = d.get("AssayInformation", {}).get("Assay", {}).get("Number of plates")
    plates = {c.plate for c in md.assay_conditions}
    if n_plates and plates and NUMERIC.match(n_plates) and int(float(n_plates)) != len(plates):
        rep.warn(
            f"Number of plates = {n_plates} but AssayConditions lists {len(plates)}: {sorted(plates)}."
        )


INLINE_CURIE = re.compile(r"\(([A-Za-z][A-Za-z0-9_.]*:[A-Za-z0-9_.-]+)\)")


def _run_lookup(*args: str) -> subprocess.CompletedProcess:
    lookup = Path(__file__).with_name("lookup_term.py")
    return subprocess.run(
        [sys.executable, "-I", str(lookup), *args], capture_output=True, text=True
    )


def _walk_strings(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)
    elif isinstance(obj, str):
        yield obj


def check_online(md: MIHCSMEMetadata, rep: Report) -> None:
    d = md.to_omero_dict()
    curies = set()
    for c in md.assay_conditions:
        for k, v in c.conditions.items():
            if k.endswith("Term Accession") and v:
                curies.add(str(v).strip())
    header = {
        k: d.get(k, {})
        for k in ("InvestigationInformation", "StudyInformation", "AssayInformation")
    }
    for text in _walk_strings(header):
        if TAXON.match(text.strip()):
            curies.add(text.strip())
        curies.update(INLINE_CURIE.findall(text))  # "CASP3 (HGNC:1504)" style values
    for curie in sorted(curies):
        prefix, local = curie.split(":", 1)
        if prefix.lower() == "cellosaurus":
            res = _run_lookup("cellline", local)
        elif prefix.lower() == "pubchem.compound":
            res = _run_lookup("compound", local)
        else:
            res = _run_lookup("resolve", curie)
        if res.returncode != 0:
            rep.error(f"Term '{curie}' did not resolve: {res.stderr.strip() or res.stdout.strip()}")
        else:
            print(f"  resolved {curie}: {res.stdout.strip().splitlines()[-1]}")

    inv = d.get("InvestigationInformation", {})
    owner = inv.get("DataOwner", {})
    people = [(owner.get("ORCID investigator"), owner.get("Last Name"))]
    people += [(o, None) for o in inv.get("DataCollaborator", {}).values()]
    for oid, last in people:
        if not oid:
            continue
        res = _run_lookup("orcid", oid)
        if res.returncode != 0:
            rep.error(f"ORCID {oid}: {res.stderr.strip()}")
            continue
        registered = res.stdout.strip().split("\t")
        print(f"  ORCID {oid}: {' '.join(registered[1:])}")
        if last and registered[-1] and _norm(last) != _norm(registered[-1]):
            rep.error(
                f"ORCID {oid} is registered to '{' '.join(registered[1:])}', "
                f"but Data Owner Last Name is '{last}'."
            )


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("file", type=Path)
    p.add_argument("--plate-format", choices=sorted(DIMS), help="Physical plate format")
    p.add_argument(
        "--online", action="store_true", help="Resolve term accessions via OLS4/Cellosaurus"
    )
    a = p.parse_args()
    rep = Report()
    try:
        md = load(a.file)
    except Exception as e:  # parse/validation failure is itself the finding
        print(f"ERROR  could not load {a.file}: {e}")
        return 1
    if not a.plate_format:
        rep.warn("No --plate-format given: well positions not checked against plate geometry.")
    check_conditions(md, a.plate_format, rep)
    check_header(md, rep)
    if a.online:
        check_online(md, rep)
    for m in rep.errors:
        print(f"ERROR  {m}")
    for m in rep.warnings:
        print(f"WARN   {m}")
    print(f"\n{len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
