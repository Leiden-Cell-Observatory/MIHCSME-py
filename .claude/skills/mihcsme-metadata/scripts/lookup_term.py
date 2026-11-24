"""Look up or verify ontology terms for MIHCSME metadata.

Searches EBI OLS4 (FBbi, EFO, NCBITaxon, ChEBI, UO, CL, BAO, GO, ...) and
Cellosaurus (cell lines). Prints candidates; never picks one for you.

Usage:
    python lookup_term.py search <ontology> "<text>" [--exact] [--rows N]
    python lookup_term.py resolve <CURIE>            # e.g. FBbi:00000253, CHEBI:15738
    python lookup_term.py cellline "<name or CVCL_xxxx>" [--rows N]
    python lookup_term.py compound "<name or CID>"   # PubChem: CID, title, InChIKey
    python lookup_term.py orcid <ORCID or URL>       # name registered for that ORCID iD

Exit code 1 when nothing is found or a CURIE does not resolve.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

OLS = "https://www.ebi.ac.uk/ols4/api"
CELLOSAURUS = "https://api.cellosaurus.org"
PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
TIMEOUT = 20


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "mihcsme-lookup/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8")


def _curie(obo_id: str | None) -> str | None:
    """OLS returns some prefixes lower-case (hgnc:1504); use the canonical form."""
    if obo_id and obo_id.lower().startswith("hgnc:"):
        return "HGNC:" + obo_id.split(":", 1)[1]
    return obo_id


def search(ontology: str, text: str, exact: bool, rows: int) -> int:
    params = {
        "q": text,
        "ontology": ontology.lower(),
        "rows": rows,
        "exact": str(exact).lower(),
        "fieldList": "obo_id,label,iri,is_obsolete,ontology_name",
    }
    data = json.loads(_get(f"{OLS}/search?{urllib.parse.urlencode(params)}"))
    docs = data["response"]["docs"]
    seen = set()
    for d in docs:
        key = d.get("iri")
        if key in seen:
            continue
        seen.add(key)
        flag = " OBSOLETE" if d.get("is_obsolete") else ""
        print(f"{_curie(d.get('obo_id'))}\t{d.get('label')}\t{d.get('iri')}{flag}")
    if not docs:
        print(f"No match for '{text}' in {ontology}", file=sys.stderr)
        return 1
    return 0


def resolve(curie: str) -> int:
    params = {
        "q": curie,
        "queryFields": "obo_id",
        "exact": "true",
        "rows": 5,
        "fieldList": "obo_id,label,iri,is_obsolete,ontology_name,is_defining_ontology",
    }
    data = json.loads(_get(f"{OLS}/search?{urllib.parse.urlencode(params)}"))
    docs = [d for d in data["response"]["docs"] if d.get("obo_id", "").lower() == curie.lower()]
    defining = [d for d in docs if d.get("is_defining_ontology")] or docs
    if not defining:
        print(f"UNRESOLVED: {curie}", file=sys.stderr)
        return 1
    d = defining[0]
    flag = " OBSOLETE" if d.get("is_obsolete") else ""
    print(f"{_curie(d['obo_id'])}\t{d['label']}\t{d['iri']}{flag}")
    return 1 if flag else 0


def _norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _cellosaurus_rows(url: str) -> list[str]:
    lines = [ln for ln in _get(url).splitlines() if ln and not ln.startswith("#")]
    return lines[1:]  # drop header


def cellline(text: str, rows: int) -> int:
    fields = "fields=id,ac,sy,ox,problem&format=tsv"
    if text.upper().startswith("CVCL_"):
        found = _cellosaurus_rows(f"{CELLOSAURUS}/cell-line/{text.upper()}?{fields}")
    else:
        found = []
        for field in ("id", "sy"):
            q = urllib.parse.quote(f'{field}:"{text}"')
            for ln in _cellosaurus_rows(
                f"{CELLOSAURUS}/search/cell-line?q={q}&{fields}&rows={rows}"
            ):
                if ln not in found:
                    found.append(ln)

        # Exact name/synonym matches first; partial matches are only candidates.
        def exact(ln: str) -> bool:
            cols = ln.split("\t")
            names = [cols[0]] + [s.strip() for s in cols[2].split(";")]
            return any(_norm(n) == _norm(text) for n in names)

        found.sort(key=lambda ln: not exact(ln))
        found = [("EXACT\t" if exact(ln) else "partial\t") + ln for ln in found]
    if not found:
        print(f"No Cellosaurus match for '{text}'", file=sys.stderr)
        return 1
    print(
        "match\tid\tac\tsynonyms\tspecies\tproblem"
        if not text.upper().startswith("CVCL_")
        else "id\tac\tsynonyms\tspecies\tproblem"
    )
    for ln in found[:rows]:
        print(ln)
    return 0


def compound(text: str) -> int:
    key = "cid" if text.isdigit() else "name"
    url = f"{PUBCHEM}/{key}/{urllib.parse.quote(text)}/property/Title,InChIKey/JSON"
    try:
        props = json.loads(_get(url))["PropertyTable"]["Properties"]
    except urllib.error.HTTPError:
        print(f"No PubChem match for '{text}'", file=sys.stderr)
        return 1
    print("CURIE\ttitle\tInChIKey")
    for d in props[:5]:
        print(f"pubchem.compound:{d['CID']}\t{d.get('Title')}\t{d.get('InChIKey')}")
    return 0


def orcid(text: str) -> int:
    oid = text.rstrip("/").rsplit("/", 1)[-1]
    req = urllib.request.Request(
        f"https://pub.orcid.org/v3.0/{oid}/person",
        headers={"Accept": "application/json", "User-Agent": "mihcsme-lookup/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            name = json.loads(resp.read().decode("utf-8")).get("name") or {}
    except urllib.error.HTTPError:
        print(f"ORCID {oid} not found", file=sys.stderr)
        return 1
    given = (name.get("given-names") or {}).get("value", "")
    family = (name.get("family-name") or {}).get("value", "")
    print(f"https://orcid.org/{oid}\t{given}\t{family}")
    if oid == "0000-0002-1825-0097":
        print(
            "WARNING: this is ORCID's public test record (Josiah Carberry), not a real researcher.",
            file=sys.stderr,
        )
        return 1
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("ontology")
    s.add_argument("text")
    s.add_argument("--exact", action="store_true")
    s.add_argument("--rows", type=int, default=5)
    r = sub.add_parser("resolve")
    r.add_argument("curie")
    c = sub.add_parser("cellline")
    c.add_argument("text")
    c.add_argument("--rows", type=int, default=5)
    m = sub.add_parser("compound")
    m.add_argument("text")
    o = sub.add_parser("orcid")
    o.add_argument("text")
    a = p.parse_args()
    try:
        if a.cmd == "search":
            return search(a.ontology, a.text, a.exact, a.rows)
        if a.cmd == "resolve":
            return resolve(a.curie)
        if a.cmd == "orcid":
            return orcid(a.text)
        if a.cmd == "compound":
            return compound(a.text)
        return cellline(a.text, a.rows)
    except OSError as e:
        print(
            f"Lookup service unreachable: {e}. Do not guess IDs; mark them unresolved.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
