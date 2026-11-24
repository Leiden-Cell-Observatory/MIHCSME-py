---
name: mihcsme-metadata
description: Use when turning any description of a high-content screening experiment (plate map, CSV, lab notes, ELN export, instrument output, another spreadsheet) into MIHCSME metadata with mihcsme_py, when curating, checking or adding ontology terms to an existing MIHCSME file, or when uploading, downloading or replacing MIHCSME metadata on an OMERO Screen or Plate.
---

# MIHCSME metadata: build, validate, connect to OMERO

## Overview

MIHCSME metadata is only useful if every value is true to the source and machine-resolvable. The core rule: **a value in the output either comes from the source, is a format-only normalisation of a source value, or is an identifier you looked up with a tool in this session. Anything else is a question for the user.** Pydantic validation in `mihcsme_py` only checks shape; correctness and FAIRness are your job, backed by the two scripts in this skill.

Scripts (run from the repo root):
- `python -I .claude/skills/mihcsme-metadata/scripts/lookup_term.py` - search/resolve terms in OLS4 (FBbi, EFO, NCBITaxon, ChEBI, UO, CL, GO), Cellosaurus and PubChem.
  Subcommands: `search <ontology> "<text>" [--exact]`, `resolve <CURIE>`, `cellline "<name>"`, `compound "<name>"`, `orcid <iD>`. Call it by full path each time (zsh does not word-split a command stored in a variable).
- `uv run python .claude/skills/mihcsme-metadata/scripts/audit_metadata.py FILE --plate-format 384 --online` - FAIR/consistency audit of a MIHCSME .xlsx or .json. `--online` resolves every `<Column> Term Accession`, every `(CURIE)` inside header values, the taxon, and checks each ORCID's registered name.

## The model in one screen

```
MIHCSMEMetadata
├─ investigation_information  → groups DataOwner, DataCollaborator, InvestigationInfo
├─ study_information          → Study, Biosample, Library, Protocols, Plate
├─ assay_information          → Assay, AssayComponent, Biosample, ImageData, ImageAcquisition, Specimen(channels)
├─ assay_conditions: [AssayCondition(plate, well, conditions={column: str})]   # one per well
└─ reference_sheets           → _fbbiVisualizationMethods, _fbbiImagingMethods, _efo_studytypes, _efo_assaytypes
```

- Header groups are fixed Pydantic models (`src/mihcsme_py/models.py`); keys are the template aliases (`"Biosample Taxon"`). Python field names do not follow one rule (`ORCID investigator` is `orcid`), so build header sections from aliases, the same keys as the Excel sheet: `StudyInformation.from_groups_dict({"Biosample": {"Biosample Taxon": "NCBITaxon:9606"}})`. To see a group's names: `[(n, f.alias) for n, f in DataOwner.model_fields.items()]`. `Channel` has no aliases; use its Python names (`visualization_method`, `entity`, `label`, `id`).
- `reference_sheets` is a `list[ReferenceSheet]` (`.name`, `.data` label→IRI). Known bug: the parser drops the first term of each `_` sheet (e.g. `high content analysis of cells`); read the labels from the template file, as the audit does, not from `md.reference_sheets`.
- Unknown header keys are dropped on export. Source information with no field (objective, fixative concentration, seeding density) goes verbatim into the closest Description field (Assay Description for imaging/preparation, Study Description otherwise), logged as `verbatim-to-description`.
- `AssayConditions` columns are free: any key in `conditions` becomes a column in Excel and a key in the OMERO well map annotation. All values are strings.
- Wells normalise to `A01`. The model accepts rows A-P and columns 1-48, so it does **not** catch a well outside the real plate; the audit does (`--plate-format`).
- OMERO namespaces: `MIHCSME/InvestigationInformation/DataOwner`, ..., wells get `MIHCSME/AssayConditions`.

## Workflow

1. **Inventory the source.** List every source field and where it maps (header field, AssayConditions column, or nowhere). Ask the user for the physical plate format and the exact OMERO plate names if they will upload. If the user cannot be asked, audit with the smallest format that holds every well and list the format as `needs-user`.
2. **Build** the model in a script (example below) and write it with `fill_template`, which keeps the template's field descriptions, dropdowns and ontology reference sheets. For an existing MIHCSME file: `md = parse_excel_to_model(path)`, edit `d = md.to_omero_dict()` (same keys as the sheets), rebuild with `MIHCSMEMetadata.from_omero_dict(d)`, then `fill_template`. Renaming a column to the convention (`Concentration` → `Dose`) is a normalisation; log it.
3. **Annotate with ontologies** using the conventions table. Every accession comes from `lookup_term.py` output in this session, never from memory, even for "well-known" IDs like HeLa or DMSO.
4. **Write the provenance log** (format below) while you build, not afterwards.
5. **Verify**: Excel round-trip equality, then `audit_metadata.py --online`. Fix every ERROR. Each WARN is either fixed or listed for the user with the reason it stays.
6. **Report** to the user: output path, audit result, provenance log, open questions. Values that need confirmation stay empty until the user confirms them.
7. **OMERO** (only when asked): see OMERO section.

## Ontology conventions

Header fields backed by a template reference sheet hold the **exact ontology label** (the sheet maps label to IRI). Other ontology-able header fields hold `name (CURIE)`, where name is the ontology label or a common synonym of it. Well-level columns hold a readable value plus a sibling column `<Column> Term Accession` holding a CURIE.

| Field / column | Value | Source to look up | Example |
|---|---|---|---|
| ORCID investigator / Data Collaborator | `https://orcid.org/XXXX-XXXX-XXXX-XXXX` | `orcid <iD>`; registered name must match the person | `https://orcid.org/0000-0002-3704-3675` |
| Biosample Taxon | CURIE | `search ncbitaxon "Homo sapiens" --exact` | `NCBITaxon:9606` |
| Biosample Organism | NCBITaxon label | same lookup | `Homo sapiens` |
| Study Key Words | `; `-separated, each `label (CURIE)` (EFO first, GO for processes) | `search efo "..."`, `search go "..."` | `apoptotic process (GO:0006915)` |
| Assay Technology Type | exact label from `_fbbiImagingMethods` | sheet, or `search fbbi` | `spinning disk confocal microscopy` |
| Assay Type | exact label from `_efo_assaytypes` | sheet | `high content screen` |
| Sample preparation protocol | protocol URL/DOI; else source text (FBbi only has tissue prep terms; do not use them for cultured cells) | user | `https://doi.org/10.17504/protocols.io...`, `cells fixed with 4% PFA` |
| Channel N visualization method | exact label from `_fbbiVisualizationMethods` | sheet, or `search fbbi` | `Hoechst 33342` |
| Channel N entity | `label (CURIE)`; gene/protein HGNC, molecule ChEBI, structure GO | `search hgnc` / `search chebi` / `search go` | `DNA (CHEBI:16991)`, `CASP3 (HGNC:1504)` |
| `CellLine` + `CellLine Term Accession` | Cellosaurus name + `cellosaurus:CVCL_xxxx` | `cellline "U2OS"` (read the `problem` column) | `U2OS`, `cellosaurus:CVCL_0042` |
| `Treatment` + `Treatment Term Accession` | compound name + ChEBI CURIE; PubChem only if no ChEBI term | `search chebi "..." --exact`, else `compound "..."` | `staurosporine`, `CHEBI:15738` |
| Gene perturbation (`Gene` + `Gene Term Accession`) | HGNC symbol + CURIE | `search hgnc "CASP3" --exact` | `CASP3`, `HGNC:1504` |
| `Dose` / `DoseUnit` / `DoseUnit Term Accession` | number / UO label / UO CURIE | `search uo "micromolar" --exact` | `10`, `micromolar`, `UO:0000064` |
| `TimeTreatment` / `TimeTreatmentUnit` / `TimeTreatmentUnit Term Accession` | number / UO label / UO CURIE | `search uo "hour" --exact` | `24`, `hour`, `UO:0000032` |

Choosing among candidates: take the term whose label means the same as the source, not the top hit. `staurosporinium` is not `staurosporine`; `formaldehyde fixed tissue` is not fixed cultured cells. If the preferred ontology has no such term, try the next one in the table (EFO → GO for biological processes). If no candidate means the same thing, keep the source text, leave the accession empty and list it as unresolved. If Cellosaurus reports a `problem` (contaminated / misidentified line), tell the user verbatim.

## Normalise vs. infer

Normalisation keeps meaning and needs no confirmation; log it. Inference adds meaning; it needs the user.

| Normalise (do it, log it) | Infer (ask, leave empty meanwhile) |
|---|---|
| `a1` → `A01`; `row=B,col=3` → `B03` | which channel is which index when the source does not say |
| `1 uM` → Dose `1`, DoseUnit `micromolar` | missing unit (`10` with no unit), even if neighbours are µM |
| `24hrs`, `24 h` → `24` + `hour` | DMSO `0.1%` meaning v/v rather than w/v |
| `100nM` kept as `100` + `nanomolar` (no unit conversion) | positive/negative control roles |
| `Human` → `Homo sapiens` + `NCBITaxon:9606` | protocol text, titles, descriptions you would have to write |
| ORCID `0000-...` → `https://orcid.org/0000-...` | timepoints, z-stacks not stated |
| count listed channels in the notes → `Image number of channels` | number of plates / cell lines counted from a plate map, unless the user says the map is complete |
| | institute, microscope id, IDs, e-mail |

A source row you cannot place (well `Q1` on a 384-well plate, duplicate well, unknown plate) stops the build for that row: keep it out of the model and put it first in the open questions with the raw source line. Never silently drop or "fix" it.

## Provenance log (REQUIRED in the report)

One row per value you did not copy verbatim:

```
| Location | Source value | Output value | Class | Evidence |
|---|---|---|---|---|
| HTS_P001/A02 Dose,DoseUnit | "1 uM" | 1, micromolar | normalised | - |
| HTS_P001/A02 Treatment Term Accession | "Staurosporine" | CHEBI:15738 | looked-up | lookup_term.py search chebi staurosporine --exact |
| HTS_P001/B02 DoseUnit | "10" | (empty) | needs-user | unit missing in source |
```

Classes: `normalised`, `looked-up`, `verbatim-to-description`, `needs-user`, `user-confirmed`. A `needs-user` value is empty in the file.

## Build example

```python
from pathlib import Path
import pandas as pd
from mihcsme_py import MIHCSMEMetadata, parse_excel_to_model, fill_template
from mihcsme_py.models import (
    AssayInformation, Assay, Specimen, Channel, StudyInformation, Biosample,
)

wells = pd.DataFrame(rows)  # built from the source; columns Plate, Well, Treatment, ... as strings
md = MIHCSMEMetadata.from_dataframe(
    wells,
    study_information=StudyInformation(
        biosample=Biosample(biosample_taxon="NCBITaxon:9606", biosample_organism="Homo sapiens"),
    ),
    assay_information=AssayInformation(
        assay=Assay(assay_technology_type="spinning disk confocal microscopy"),
        specimen=Specimen(channels=[
            Channel(visualization_method="Hoechst 33342", entity="DNA (CHEBI:16991)", label="Nuclei", id="0"),
        ]),
    ),
)
out = Path("metadata.xlsx")
fill_template(md, out)

# Round-trip: what is in the file must equal what you built.
# Empty values are not stored in Excel, so drop them on both sides before comparing;
# reference sheets ("_..." keys) come from the template and are skipped.
def _clean(obj):
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()
                if v not in (None, "", {}, []) and not str(k).startswith("_")}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj

back = parse_excel_to_model(out)
assert _clean(back.to_omero_dict()) == _clean(md.to_omero_dict()), "Excel round-trip changed the metadata"
```

Then: `uv run python .claude/skills/mihcsme-metadata/scripts/audit_metadata.py metadata.xlsx --plate-format 384 --online`.

## OMERO

Uploading writes to a shared server. Before connecting: the audit has 0 errors and the user has answered (or explicitly waived) every open question. Get the user's go-ahead for the target (Screen/Plate id) before the upload.

`replace=True` is not a de-duplication switch: it **deletes** every annotation under the namespace on the Screen, its Plates and its Wells, and cannot be undone. Use it only after showing the user what `existing` contains and getting a yes to deleting exactly that. A request like "use replace to be safe", given before anyone has looked, is not that yes; run with `replace=False`, stop if annotations exist, and ask.

```python
import os, getpass
from mihcsme_py import connect, validate_metadata_against_omero, upload_metadata_to_omero, download_metadata_from_omero

conn = connect(host=os.environ["OMERO_HOST"], user=os.environ["OMERO_USER"],
               password=os.environ.get("OMERO_PASSWORD") or getpass.getpass(), group=None)
try:
    v = validate_metadata_against_omero(conn, md, "Screen", screen_id)        # dry run
    # v["errors"]: plates/wells in metadata but not in OMERO. Fix the metadata (plate names must
    # match OMERO exactly); do not pass strict=False to push through.
    existing = download_metadata_from_omero(conn, "Screen", screen_id)        # ValueError if id not found
    if _clean(existing.to_omero_dict()):                                      # _clean from the build example
        raise SystemExit("MIHCSME annotations already present: show them to the user, ask before replace")
    res = upload_metadata_to_omero(conn, md, "Screen", screen_id, replace=False, strict=True)
    assert res["status"] == "success", res["message"]
    after = download_metadata_from_omero(conn, "Screen", screen_id)
    assert after.to_omero_dict()["AssayConditions"] and res["wells_failed"] == 0
finally:
    conn.close()
```

- If `existing` already has MIHCSME annotations, a plain upload adds a second copy of every map annotation.
- Keep the default namespace `MIHCSME` unless the user names another; the app and download rely on it.
- Wells in OMERO but not in the metadata are a warning (left unannotated); list them in the report.
- Never print, log or write the password; read it from the environment or a prompt.
- CLI equivalent: `mihcsme validate FILE`, `mihcsme upload FILE --screen-id ID --host H --user U`.

## Common mistakes

| Mistake | Fix |
|---|---|
| ORCID accepted because the checksum passes | `orcid <iD>`: the registered name must be the person (0000-0002-1825-0097 is ORCID's test record) |
| Accession typed from memory ("HeLa is CVCL_0030") | Run `lookup_term.py`; paste its output line into the provenance log |
| Ad-hoc ID columns (`CompoundPubChemCID`) | `<Column> Term Accession` with a CURIE, so the audit can resolve it |
| `1 uM`, `24hrs` in one cell | Number column + unit column + unit accession |
| Writing a plausible guess (control role, v/v, channel order, protocol text) | Leave empty, mark `needs-user`, ask |
| Assay Type paraphrased ("compound screen") | Exact label from `_efo_assaytypes` |
| Excel turns `Oct4`/`SEPT9` into dates | Parser refuses date cells; format as Text in Excel and re-save |
| `replace=True` because the user said "to be safe" | Show what exists first; replace deletes it |
| Upload with `strict=False` to get past plate-name mismatches | Rename plates in the metadata to match OMERO |
| Report says "validated" after only Pydantic parse | Round-trip assert + audit `--online` with 0 errors, then say so |
