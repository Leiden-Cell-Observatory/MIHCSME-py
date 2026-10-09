# Flagship marimo app Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `examples/marimo/marimo_omero_app.py` into a single, better flagship app (`mihcsme_app.py`) with an interactive plate editor, generated metadata forms and a per-plate OMERO status table, and slim the examples down to the flagship plus three short notebooks.

**Architecture:** Testable logic moves into the package: `mihcsme_py/plate_ops.py` (pure pandas), `mihcsme_py/widgets/` (anywidget `PlateViewer` with Python-side edit handling), `mihcsme_py/forms.py` (Pydantic model ⇄ marimo form). The app keeps its existing structure (Load / Wells / Metadata / Export / OMERO tabs, LLM and OMERO download features) and only swaps the wells tab, the metadata form cells and the OMERO validation display. Old app is moved with `git mv`, not rewritten.

**Tech Stack:** Python ≥3.9 (package), marimo ≥0.19.6, anywidget, traitlets, pandas, pydantic v2, pytest, playwright (smoke test only).

**Spec:** `docs/superpowers/specs/2026-10-08-flagship-app-design.md`

## Global Constraints

- Core dependencies stay `pandas`, `pydantic`, `openpyxl`. New optional extra: `app = ["anywidget>=0.9", "marimo>=0.19.6"]`.
- Plate formats: 96 (8×12, rows A–H) and 384 (16×24, rows A–P) only.
- Well names are normalised like `AssayCondition` does (`a1` → `A01`).
- Cells that push data to the widget must not depend on the selection (performance rule from the spike).
- `examples/marimo/marimo_bia.py` contains credentials: never `git add` it, never `git add -A` / `git add .` in `examples/`.
- marimo notebook edits: only change code inside `@app.cell` functions; marimo manages parameters/returns. Run `uvx marimo check --fix <file>` after editing a notebook.
- Test command: `uv run --extra dev --extra cli --extra app pytest tests/ -v` (CI uses `--extra dev --extra cli`; Task 1 adds `--extra app` to CI).
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Spec deviations (decided while planning)

- Example data: the bundled `templates/LEI-MIHCSME.xlsx` has no wells, so the app's default file and `01` use a copy of the tracked `MIHCSME Template_example.xlsx` (72 wells, filled sections) bundled as `src/mihcsme_py/templates/MIHCSME_example.xlsx`.
- `validate_metadata_against_omero` gains an `omero_plates` key (sorted OMERO plate names, empty when the target is missing) so the status table never guesses.
- The app loads the example by default (File Path mode pre-filled with the bundled example) instead of a separate "Load example" button.

## Review Focus

1. Wells written as `a1` / `A1` in Excel: plate editor must place them at A01, not drop them. → Task 1 `test_widget_payload_normalises_well_names`.
2. Missing values (`NaN`) in condition columns: payload must contain `None`, never `NaN` (breaks JSON in the browser). → Task 1 `test_widget_payload_nan_becomes_none`.
3. A well outside the detected grid (e.g. `Q01` typo, or column 30): must not shift other wells; payload length is always rows×cols. → Task 1 `test_widget_payload_ignores_wells_outside_grid`.
4. User types an invalid ORCID in the form: inline error, app keeps working, export uses the last valid data. → Task 4 `test_form_to_model_returns_error_for_bad_orcid`.
5. OMERO target ID does not exist: status table must show plates as *not* in OMERO. → Task 2 `test_plate_status_target_missing`.

---

## File structure

```
src/mihcsme_py/
  plate_ops.py               Task 1, 2  pure dataframe functions
  widgets/__init__.py        Task 3     exports PlateViewer, ImportError hint
  widgets/plate_viewer.py    Task 3     anywidget class + edit/undo handling
  widgets/plate_viewer.js    Task 3     frontend
  forms.py                   Task 4     pydantic <-> marimo form helpers
  uploader.py                Task 2     add omero_plates to validation result
  templates/MIHCSME_example.xlsx  Task 5  example data
tests/
  test_plate_ops.py          Task 1, 2
  test_plate_viewer.py       Task 3
  test_forms.py              Task 4
  test_uploader.py           Task 2 (one new test)
  test_app_smoke.py          Task 9
examples/marimo/
  mihcsme_app.py             Task 5-7 (git mv from marimo_omero_app.py)
  01_parse_and_explore.py    Task 8
  02_omero_roundtrip.py      Task 8
  03_llm_fill.py             Task 8
```

---

### Task 1: `[app]` extra and `plate_ops` core functions

**Files:**
- Modify: `pyproject.toml` (optional-dependencies, pytest markers)
- Modify: `.github/workflows/ci.yml:35`
- Create: `src/mihcsme_py/plate_ops.py`
- Test: `tests/test_plate_ops.py`

**Interfaces:**
- Produces:
  - `normalize_well(well: str) -> str | None` — `"a1"` → `"A01"`; returns `None` for invalid names.
  - `plate_dims(plate_format: str) -> tuple[int, int]` — `"96"` → `(8, 12)`, `"384"` → `(16, 24)`.
  - `detect_format(wells: Iterable[str]) -> Literal["96", "384"]`
  - `apply_edit(df: pd.DataFrame, plate: str, wells: list[str], field: str, value: str | None) -> pd.DataFrame`
  - `widget_payload(df: pd.DataFrame, color_field: str | None, plate_format: str) -> dict` with keys `plates: list[str]`, `fields: list[str]`, `values: dict[str, list[str | None]]`
  - `detail_payload(df: pd.DataFrame, plate: str) -> dict[str, dict[str, str]]`

- [ ] **Step 1: Add the extra, marker and CI flag**

In `pyproject.toml` under `[project.optional-dependencies]`, after the `llm` block, add:

```toml
# Interactive marimo app (plate editor widget)
app = [
    "anywidget>=0.9",
    "marimo>=0.19.6",
]
```

In the same file, add a `markers` entry to `[tool.pytest.ini_options]` (needed because of `--strict-markers`):

```toml
markers = [
    "slow: browser-based smoke tests (deselect with '-m \"not slow\"')",
]
```

In `.github/workflows/ci.yml` line 35 change the run command to:

```yaml
      run: uv run --extra dev --extra cli --extra app pytest tests/ -v -m "not slow"
```

Then run `uv lock` to update `uv.lock`.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_plate_ops.py`:

```python
"""Tests for plate_ops: pure dataframe helpers behind the plate editor."""

import math

import pandas as pd
import pytest

from mihcsme_py import plate_ops


def _df():
    return pd.DataFrame(
        {
            "Plate": ["P1", "P1", "P1", "P2"],
            "Well": ["A01", "A02", "B01", "A01"],
            "Treatment": ["DMSO", "CPD1", "CPD2", "DMSO"],
            "Dose": ["0.1", "1", "10", "0.1"],
        }
    )


class TestNormalizeWell:
    def test_pads_and_uppercases(self):
        assert plate_ops.normalize_well("a1") == "A01"
        assert plate_ops.normalize_well(" B12 ") == "B12"

    def test_invalid_returns_none(self):
        assert plate_ops.normalize_well("Q01") is None
        assert plate_ops.normalize_well("") is None
        assert plate_ops.normalize_well("A") is None


class TestDetectFormat:
    def test_96(self):
        assert plate_ops.detect_format(["A01", "H12"]) == "96"

    def test_384_by_row(self):
        assert plate_ops.detect_format(["A01", "I01"]) == "384"

    def test_384_by_column(self):
        assert plate_ops.detect_format(["A13"]) == "384"

    def test_empty_defaults_to_96(self):
        assert plate_ops.detect_format([]) == "96"


class TestApplyEdit:
    def test_sets_value_on_selected_wells_only(self):
        out = plate_ops.apply_edit(_df(), "P1", ["A01", "B01"], "Treatment", "X")
        assert out["Treatment"].tolist() == ["X", "CPD1", "X", "DMSO"]

    def test_does_not_mutate_input(self):
        df = _df()
        plate_ops.apply_edit(df, "P1", ["A01"], "Treatment", "X")
        assert df["Treatment"].tolist() == ["DMSO", "CPD1", "CPD2", "DMSO"]

    def test_new_field_is_added(self):
        out = plate_ops.apply_edit(_df(), "P1", ["A01"], "CellLine", "HeLa")
        assert out.loc[0, "CellLine"] == "HeLa"
        assert out["CellLine"].isna().sum() == 3

    def test_empty_value_unsets(self):
        out = plate_ops.apply_edit(_df(), "P1", ["A01"], "Treatment", "")
        assert pd.isna(out.loc[0, "Treatment"])

    def test_unknown_wells_are_ignored(self):
        out = plate_ops.apply_edit(_df(), "P1", ["H12"], "Treatment", "X")
        assert out["Treatment"].tolist() == ["DMSO", "CPD1", "CPD2", "DMSO"]

    def test_normalises_requested_wells(self):
        out = plate_ops.apply_edit(_df(), "P1", ["a1"], "Treatment", "X")
        assert out.loc[0, "Treatment"] == "X"


class TestWidgetPayload:
    def test_shape(self):
        p = plate_ops.widget_payload(_df(), "Treatment", "96")
        assert p["plates"] == ["P1", "P2"]
        assert p["fields"] == ["Treatment", "Dose"]
        assert len(p["values"]["P1"]) == 96
        assert p["values"]["P1"][0] == "DMSO"  # A01
        assert p["values"]["P1"][1] == "CPD1"  # A02
        assert p["values"]["P1"][12] == "CPD2"  # B01
        assert p["values"]["P1"][2] is None

    def test_values_are_strings(self):
        df = _df().assign(Dose=[0.1, 1, 10, 0.1])
        p = plate_ops.widget_payload(df, "Dose", "96")
        assert p["values"]["P1"][0] == "0.1"

    def test_widget_payload_nan_becomes_none(self):
        df = _df()
        df.loc[0, "Treatment"] = float("nan")
        p = plate_ops.widget_payload(df, "Treatment", "96")
        assert p["values"]["P1"][0] is None
        assert not any(isinstance(v, float) and math.isnan(v) for v in p["values"]["P1"])

    def test_widget_payload_normalises_well_names(self):
        df = _df().assign(Well=["a1", "A2", "b1", "A1"])
        p = plate_ops.widget_payload(df, "Treatment", "96")
        assert p["values"]["P1"][0] == "DMSO"
        assert p["values"]["P1"][12] == "CPD2"

    def test_widget_payload_ignores_wells_outside_grid(self):
        df = _df().assign(Well=["A01", "A30", "Q01", "A01"])
        p = plate_ops.widget_payload(df, "Treatment", "96")
        assert len(p["values"]["P1"]) == 96
        assert p["values"]["P1"][0] == "DMSO"
        assert p["values"]["P1"].count(None) == 95

    def test_no_color_field_gives_all_none(self):
        p = plate_ops.widget_payload(_df(), None, "96")
        assert set(p["values"]["P1"]) == {None}

    def test_empty_dataframe(self):
        p = plate_ops.widget_payload(pd.DataFrame(), None, "96")
        assert p == {"plates": [], "fields": [], "values": {}}


class TestDetailPayload:
    def test_current_plate_only_and_strings(self):
        d = plate_ops.detail_payload(_df(), "P1")
        assert set(d) == {"A01", "A02", "B01"}
        assert d["A01"] == {"Treatment": "DMSO", "Dose": "0.1"}

    def test_drops_missing_values(self):
        df = _df()
        df.loc[0, "Dose"] = None
        assert plate_ops.detail_payload(df, "P1")["A01"] == {"Treatment": "DMSO"}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run --extra dev --extra cli --extra app pytest tests/test_plate_ops.py -v`
Expected: FAIL / collection error — `cannot import name 'plate_ops'`.

- [ ] **Step 4: Implement `plate_ops.py`**

Create `src/mihcsme_py/plate_ops.py`:

```python
"""Pure dataframe helpers for the plate editor.

The well dataframe has columns ``Plate``, ``Well`` and one column per
condition field (Treatment, Dose, ...), as produced by
``MIHCSMEMetadata.to_dataframe()``.
"""

from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple

import pandas as pd

from mihcsme_py.models import AssayCondition

PlateFormat = Literal["96", "384"]
_DIMS = {"96": (8, 12), "384": (16, 24)}
_KEY_COLUMNS = ("Plate", "Well")


def normalize_well(well: str) -> Optional[str]:
    """Normalise a well name like ``a1`` to ``A01``; ``None`` if invalid."""
    try:
        return AssayCondition(plate="_", well=str(well)).well
    except ValueError:
        return None


def plate_dims(plate_format: str) -> Tuple[int, int]:
    """Return (rows, columns) for a plate format."""
    return _DIMS[plate_format]


def _row_col(well: str) -> Tuple[int, int]:
    return ord(well[0]) - ord("A"), int(well[1:]) - 1


def detect_format(wells: Iterable[str]) -> PlateFormat:
    """Return "384" if any well lies outside an 8x12 grid, else "96"."""
    for well in wells:
        name = normalize_well(well)
        if name is None:
            continue
        row, col = _row_col(name)
        if row >= 8 or col >= 12:
            return "384"
    return "96"


def _is_missing(value: Any) -> bool:
    return value is None or (not isinstance(value, str) and pd.isna(value))


def _as_str(value: Any) -> Optional[str]:
    return None if _is_missing(value) else str(value)


def apply_edit(
    df: pd.DataFrame,
    plate: str,
    wells: List[str],
    field: str,
    value: Optional[str],
) -> pd.DataFrame:
    """Return a copy of ``df`` with ``field`` set to ``value`` on the given wells.

    An empty string or ``None`` unsets the field. Unknown wells are ignored.
    """
    out = df.copy()
    if field not in out.columns:
        out[field] = None
    targets = {w for w in (normalize_well(w) for w in wells) if w}
    normalized = out["Well"].map(normalize_well)
    mask = (out["Plate"] == plate) & normalized.isin(targets)
    out[field] = out[field].astype(object)
    out.loc[mask, field] = value if value not in ("", None) else None
    return out


def widget_payload(
    df: pd.DataFrame, color_field: Optional[str], plate_format: str
) -> Dict[str, Any]:
    """Build the ``plates``/``fields``/``values`` traits for the PlateViewer.

    ``values`` maps each plate to a row-major list of ``rows*cols`` entries
    (strings or ``None``). Wells outside the grid are ignored.
    """
    if df.empty:
        return {"plates": [], "fields": [], "values": {}}
    rows, cols = plate_dims(plate_format)
    plates = sorted(df["Plate"].astype(str).unique())
    fields = [c for c in df.columns if c not in _KEY_COLUMNS]
    values: Dict[str, List[Optional[str]]] = {}
    for plate in plates:
        grid: List[Optional[str]] = [None] * (rows * cols)
        if color_field in df.columns:
            sub = df[df["Plate"].astype(str) == plate]
            for well, value in zip(sub["Well"], sub[color_field]):
                name = normalize_well(well)
                if name is None:
                    continue
                row, col = _row_col(name)
                if row < rows and col < cols:
                    grid[row * cols + col] = _as_str(value)
        values[plate] = grid
    return {"plates": plates, "fields": fields, "values": values}


def detail_payload(df: pd.DataFrame, plate: str) -> Dict[str, Dict[str, str]]:
    """Map each well of ``plate`` to its non-missing fields (as strings)."""
    if df.empty:
        return {}
    sub = df[df["Plate"].astype(str) == plate]
    fields = [c for c in df.columns if c not in _KEY_COLUMNS]
    detail: Dict[str, Dict[str, str]] = {}
    for record in sub.to_dict("records"):
        name = normalize_well(record["Well"])
        if name is None:
            continue
        detail[name] = {f: str(record[f]) for f in fields if not _is_missing(record[f])}
    return detail
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --extra dev --extra cli --extra app pytest tests/test_plate_ops.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .github/workflows/ci.yml src/mihcsme_py/plate_ops.py tests/test_plate_ops.py
git commit -m "feat: add plate_ops helpers and [app] extra for the plate editor

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: OMERO plate status table data

**Files:**
- Modify: `src/mihcsme_py/uploader.py` (`validate_metadata_against_omero`)
- Modify: `src/mihcsme_py/plate_ops.py`
- Test: `tests/test_plate_ops.py`, `tests/test_uploader.py`

**Interfaces:**
- Consumes: `normalize_well` (Task 1).
- Produces:
  - validation dict gains `"omero_plates": list[str]` (sorted; `[]` when target not found).
  - `plate_status(df: pd.DataFrame, validation: dict) -> pd.DataFrame` with columns `Plate`, `In design`, `In OMERO`, `Wells in design`, `Wells matched`, `Missing in OMERO`, `Extra in OMERO`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_plate_ops.py`:

```python
class TestPlateStatus:
    def _validation(self, **kw):
        base = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "plates": {"in_metadata_not_omero": [], "in_omero_not_metadata": []},
            "wells": {},
            "omero_plates": ["P1", "P2"],
        }
        base.update(kw)
        return base

    def test_all_matched(self):
        status = plate_ops.plate_status(_df(), self._validation())
        row = status.set_index("Plate").loc["P1"]
        assert bool(row["In design"]) and bool(row["In OMERO"])
        assert row["Wells in design"] == 3
        assert row["Wells matched"] == 3
        assert row["Missing in OMERO"] == 0

    def test_missing_wells_and_extra_plate(self):
        validation = self._validation(
            omero_plates=["P1", "P2", "P3"],
            wells={"P1": {"in_metadata_not_omero": ["B01"], "in_omero_not_metadata": ["H12", "H11"]}},
        )
        status = plate_ops.plate_status(_df(), validation).set_index("Plate")
        assert status.loc["P1", "Wells matched"] == 2
        assert status.loc["P1", "Missing in OMERO"] == 1
        assert status.loc["P1", "Extra in OMERO"] == 2
        assert not bool(status.loc["P3", "In design"])
        assert bool(status.loc["P3", "In OMERO"])

    def test_plate_status_target_missing(self):
        validation = self._validation(valid=False, errors=["Screen with ID 9 not found"], omero_plates=[])
        status = plate_ops.plate_status(_df(), validation)
        assert not status["In OMERO"].any()
        assert (status["Wells matched"] == 0).all()
```

Append to `tests/test_uploader.py` (it already mocks OMERO; reuse its existing fixtures/mocks for `validate_metadata_against_omero` — find the test class that calls `validate_metadata_against_omero` and add next to it):

```python
def test_validation_reports_omero_plates_when_target_missing(monkeypatch):
    from mihcsme_py import uploader
    from mihcsme_py.models import AssayCondition, MIHCSMEMetadata

    monkeypatch.setattr(uploader, "_get_plates_to_process", lambda conn, t, i: [])
    metadata = MIHCSMEMetadata(assay_conditions=[AssayCondition(plate="P1", well="A01")])
    result = uploader.validate_metadata_against_omero(None, metadata, "Screen", 9)
    assert result["omero_plates"] == []
    assert result["valid"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --extra dev --extra cli --extra app pytest tests/test_plate_ops.py::TestPlateStatus tests/test_uploader.py::test_validation_reports_omero_plates_when_target_missing -v`
Expected: FAIL — `AttributeError: module 'mihcsme_py.plate_ops' has no attribute 'plate_status'` and `KeyError: 'omero_plates'`.

- [ ] **Step 3: Implement**

In `src/mihcsme_py/uploader.py`, in `validate_metadata_against_omero`:

1. Add `"omero_plates": [],` to the initial `result` dict (after `"wells": {},`).
2. Update the docstring "Returns" list with: `- omero_plates: Sorted plate names found in OMERO for the target (empty if not found)`.
3. Directly after `omero_plate_names = {plate.getName() for plate in plates}` add:

```python
    result["omero_plates"] = sorted(omero_plate_names)
```

Append to `src/mihcsme_py/plate_ops.py`:

```python
def plate_status(df: pd.DataFrame, validation: Dict[str, Any]) -> pd.DataFrame:
    """Per-plate overview of how the design matches OMERO.

    Args:
        df: Well dataframe of the design.
        validation: Result of ``validate_metadata_against_omero``.
    """
    design_wells: Dict[str, set] = {}
    if not df.empty:
        for plate, well in zip(df["Plate"].astype(str), df["Well"]):
            name = normalize_well(well)
            if name:
                design_wells.setdefault(plate, set()).add(name)
    omero_plates = set(validation.get("omero_plates", []))
    rows = []
    for plate in sorted(set(design_wells) | omero_plates):
        info = validation.get("wells", {}).get(plate, {})
        n_design = len(design_wells.get(plate, ()))
        in_omero = plate in omero_plates
        missing = len(info.get("in_metadata_not_omero", [])) if in_omero else n_design
        rows.append(
            {
                "Plate": plate,
                "In design": plate in design_wells,
                "In OMERO": in_omero,
                "Wells in design": n_design,
                "Wells matched": n_design - missing,
                "Missing in OMERO": missing,
                "Extra in OMERO": len(info.get("in_omero_not_metadata", [])),
            }
        )
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --extra dev --extra cli --extra app pytest tests/test_plate_ops.py tests/test_uploader.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mihcsme_py/uploader.py src/mihcsme_py/plate_ops.py tests/test_plate_ops.py tests/test_uploader.py
git commit -m "feat: per-plate OMERO status from validation result

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `PlateViewer` anywidget

**Files:**
- Create: `src/mihcsme_py/widgets/__init__.py`
- Create: `src/mihcsme_py/widgets/plate_viewer.py`
- Create: `src/mihcsme_py/widgets/plate_viewer.js`
- Test: `tests/test_plate_viewer.py`

**Interfaces:**
- Consumes: `plate_ops.widget_payload`, `detail_payload`, `detect_format`, `apply_edit` (Task 1).
- Produces:
  - `PlateViewer()` (anywidget). Traits: `plates`, `plate_format`, `fields`, `color_field`, `values`, `detail`, `current_plate`, `selection`, `edit_request`, `can_undo`.
  - `PlateViewer.set_data(df: pd.DataFrame) -> None`
  - `PlateViewer.on_change(callback: Callable[[pd.DataFrame], None]) -> None` — called with the new dataframe after every edit or undo.
  - `PlateViewer.data -> pd.DataFrame` (property, current dataframe).
  - `edit_request` format (JS → Python): `{"id": int, "action": "set", "plate": str, "wells": [str], "field": str, "value": str}` or `{"id": int, "action": "undo"}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_plate_viewer.py`:

```python
"""Python-side behaviour of the PlateViewer widget (no browser)."""

import pandas as pd
import pytest

pytest.importorskip("anywidget")

from mihcsme_py.widgets import PlateViewer  # noqa: E402


def _df():
    return pd.DataFrame(
        {
            "Plate": ["P1", "P1", "P2"],
            "Well": ["A01", "A02", "I01"],
            "Treatment": ["DMSO", "CPD1", "DMSO"],
            "Dose": ["0.1", "1", "0.1"],
        }
    )


def test_set_data_populates_traits():
    v = PlateViewer()
    v.set_data(_df())
    assert v.plates == ["P1", "P2"]
    assert v.plate_format == "384"  # I01 forces 384
    assert v.current_plate == "P1"
    assert v.color_field == "Treatment"
    assert len(v.values["P1"]) == 384
    assert v.detail["A01"]["Treatment"] == "DMSO"


def test_changing_color_field_refreshes_values():
    v = PlateViewer()
    v.set_data(_df())
    v.color_field = "Dose"
    assert v.values["P1"][0] == "0.1"


def test_changing_plate_refreshes_detail_and_clears_selection():
    v = PlateViewer()
    v.set_data(_df())
    v.selection = ["A01"]
    v.current_plate = "P2"
    assert set(v.detail) == {"I01"}
    assert v.selection == []


def test_edit_request_applies_and_notifies():
    v = PlateViewer()
    v.set_data(_df())
    seen = []
    v.on_change(seen.append)
    v.edit_request = {"id": 1, "action": "set", "plate": "P1", "wells": ["A01"], "field": "Treatment", "value": "X"}
    assert v.data.loc[0, "Treatment"] == "X"
    assert v.values["P1"][0] == "X"
    assert len(seen) == 1 and seen[0].loc[0, "Treatment"] == "X"
    assert v.can_undo is True


def test_undo_restores_previous():
    v = PlateViewer()
    v.set_data(_df())
    seen = []
    v.on_change(seen.append)
    v.edit_request = {"id": 1, "action": "set", "plate": "P1", "wells": ["A01"], "field": "Treatment", "value": "X"}
    v.edit_request = {"id": 2, "action": "undo"}
    assert v.data.loc[0, "Treatment"] == "DMSO"
    assert v.can_undo is False
    assert seen[-1].loc[0, "Treatment"] == "DMSO"


def test_set_data_with_same_frame_keeps_undo():
    v = PlateViewer()
    v.set_data(_df())
    v.on_change(v.set_data)  # what the app does via mo.state round-trip
    v.edit_request = {"id": 1, "action": "set", "plate": "P1", "wells": ["A01"], "field": "Treatment", "value": "X"}
    assert v.can_undo is True


def test_set_data_with_new_frame_clears_undo():
    v = PlateViewer()
    v.set_data(_df())
    v.edit_request = {"id": 1, "action": "set", "plate": "P1", "wells": ["A01"], "field": "Treatment", "value": "X"}
    v.set_data(_df())
    assert v.can_undo is False


def test_empty_dataframe():
    v = PlateViewer()
    v.set_data(pd.DataFrame())
    assert v.plates == [] and v.values == {} and v.current_plate == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --extra dev --extra cli --extra app pytest tests/test_plate_viewer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mihcsme_py.widgets'`.

- [ ] **Step 3: Implement the Python side**

Create `src/mihcsme_py/widgets/__init__.py`:

```python
"""Interactive widgets for the MIHCSME marimo app (requires the ``app`` extra)."""

try:
    from mihcsme_py.widgets.plate_viewer import PlateViewer
except ImportError as e:  # pragma: no cover - depends on optional deps
    raise ImportError(
        "The plate editor needs the optional 'app' dependencies: "
        "pip install 'mihcsme-py[app]'"
    ) from e

__all__ = ["PlateViewer"]
```

Create `src/mihcsme_py/widgets/plate_viewer.py`:

```python
"""Plate editor widget: view a plate layout and edit wells by selection."""

from pathlib import Path
from typing import Callable, Optional

import anywidget
import pandas as pd
import traitlets

from mihcsme_py import plate_ops


class PlateViewer(anywidget.AnyWidget):
    """Interactive 96/384-well plate editor.

    Python owns the data: call :meth:`set_data` with the well dataframe and
    register :meth:`on_change` to receive the edited dataframe.
    """

    _esm = Path(__file__).with_name("plate_viewer.js")

    plates = traitlets.List(traitlets.Unicode()).tag(sync=True)
    plate_format = traitlets.Unicode("96").tag(sync=True)
    fields = traitlets.List(traitlets.Unicode()).tag(sync=True)
    color_field = traitlets.Unicode("").tag(sync=True)
    values = traitlets.Dict().tag(sync=True)
    detail = traitlets.Dict().tag(sync=True)
    current_plate = traitlets.Unicode("").tag(sync=True)
    selection = traitlets.List(traitlets.Unicode()).tag(sync=True)
    edit_request = traitlets.Dict().tag(sync=True)
    can_undo = traitlets.Bool(False).tag(sync=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._df = pd.DataFrame()
        self._previous: Optional[pd.DataFrame] = None
        self._callback: Optional[Callable[[pd.DataFrame], None]] = None
        self.observe(self._on_color_field, names=["color_field"])
        self.observe(self._on_current_plate, names=["current_plate"])
        self.observe(self._on_edit_request, names=["edit_request"])

    @property
    def data(self) -> pd.DataFrame:
        """The current well dataframe."""
        return self._df

    def on_change(self, callback: Callable[[pd.DataFrame], None]) -> None:
        """Register a callback that receives the dataframe after each edit/undo."""
        self._callback = callback

    def set_data(self, df: pd.DataFrame) -> None:
        """Show ``df``. A different dataframe object clears the undo step."""
        if df is not self._df:
            self._previous = None
            self.can_undo = False
        self._df = df
        wells = df["Well"].tolist() if "Well" in df.columns else []
        self.plate_format = plate_ops.detect_format(wells)
        fields = [c for c in df.columns if c not in ("Plate", "Well")]
        if self.color_field not in fields:
            self.color_field = fields[0] if fields else ""
        self._push_values()
        if self.current_plate not in self.plates:
            self.current_plate = self.plates[0] if self.plates else ""
        self._push_detail()

    def _push_values(self) -> None:
        payload = plate_ops.widget_payload(self._df, self.color_field or None, self.plate_format)
        self.fields = payload["fields"]
        self.values = payload["values"]
        self.plates = payload["plates"]

    def _push_detail(self) -> None:
        self.detail = plate_ops.detail_payload(self._df, self.current_plate)

    def _on_color_field(self, _change) -> None:
        self._push_values()

    def _on_current_plate(self, _change) -> None:
        self.selection = []
        self._push_detail()

    def _on_edit_request(self, change) -> None:
        request = change["new"] or {}
        action = request.get("action")
        if action == "undo":
            if self._previous is None:
                return
            new_df, self._previous = self._previous, None
        elif action == "set":
            new_df = plate_ops.apply_edit(
                self._df,
                request["plate"],
                request.get("wells", []),
                request["field"],
                request.get("value"),
            )
            self._previous = self._df
        else:
            return
        self._df = new_df
        self.can_undo = self._previous is not None
        self._push_values()
        self._push_detail()
        if self._callback is not None:
            self._callback(new_df)
```

- [ ] **Step 4: Implement the frontend**

Create `src/mihcsme_py/widgets/plate_viewer.js` (behaviour matches the brainstorm mockup):

```javascript
const PALETTE = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948", "#b07aa1",
  "#ff9da7", "#9c755f", "#bab0ac", "#1f77b4", "#aec7e8", "#ffbb78", "#98df8a", "#c5b0d5",
  "#c49c94", "#f7b6d2", "#dbdb8d", "#9edae5", "#393b79"];
const NS = "http://www.w3.org/2000/svg";
const CSS = `
.pv { font-family: system-ui, sans-serif; user-select: none; font-size: 12px;
  --pv-unset: #ffffff; --pv-line: #9aa0a6; --pv-sel: #111; --pv-hover: rgba(127,127,127,.15); }
@media (prefers-color-scheme: dark) { .pv { --pv-unset: #2a2a2a; --pv-line: #666; --pv-sel: #fff; } }
:host-context(.dark) .pv, .dark .pv { --pv-unset: #2a2a2a; --pv-line: #666; --pv-sel: #fff; }
.pv-bar { display: flex; gap: 12px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
.pv-thumbs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.pv-thumb { font-size: 10px; text-align: center; cursor: pointer; }
.pv-thumb canvas { border: 2px solid transparent; border-radius: 3px; display: block; }
.pv-thumb.cur canvas { border-color: var(--pv-sel); }
.pv-main { display: flex; gap: 20px; align-items: flex-start; flex-wrap: wrap; }
.pv-side { width: 260px; }
.pv-legend { max-height: 300px; overflow: auto; border: 1px solid var(--pv-line); border-radius: 6px; padding: 6px; }
.pv-li { display: flex; align-items: center; gap: 6px; padding: 2px 4px; border-radius: 4px; cursor: pointer; }
.pv-li:hover { background: var(--pv-hover); }
.pv-sw { width: 12px; height: 12px; border-radius: 6px; flex: none; }
.pv-cnt { margin-left: auto; opacity: .6; }
.pv-edit { margin-top: 12px; border: 1px solid var(--pv-line); border-radius: 6px; padding: 8px;
  display: flex; flex-direction: column; gap: 6px; }
.pv-label { font-size: 11px; text-transform: uppercase; opacity: .7; }
.pv-grad { height: 10px; border-radius: 3px; margin: 4px 0; }
.pv-hdr { cursor: pointer; font-size: 10px; fill: currentColor; }
.pv-hdr:hover { font-weight: bold; }
.pv-tip { position: fixed; pointer-events: none; background: #222; color: #fff; font-size: 11px;
  padding: 4px 6px; border-radius: 4px; display: none; white-space: pre; z-index: 1000; }
.pv-empty { opacity: .7; padding: 12px; }
`;

const wellName = (r, c) => String.fromCharCode(65 + r) + String(c + 1).padStart(2, "0");
const dims = (fmt) => (fmt === "384" ? [16, 24] : [8, 12]);
const isUnset = (v) => v === null || v === undefined || v === "";
const gradColor = (t) => `hsl(${220 - 200 * t} 70% ${85 - 45 * t}%)`;

function buildScale(model) {
  const all = [];
  for (const p of model.get("plates")) for (const v of model.get("values")[p] || []) if (!isUnset(v)) all.push(v);
  const nums = all.map(Number).filter((n) => !Number.isNaN(n));
  if (all.length && nums.length / all.length >= 0.9) {
    const pos = nums.filter((n) => n > 0);
    const logs = pos.map(Math.log10);
    const lo = logs.length ? Math.min(...logs) : 0;
    const hi = logs.length ? Math.max(...logs) : 0;
    return {
      numeric: true, lo: Math.pow(10, lo), hi: Math.pow(10, hi),
      color: (v) => {
        const n = Number(v);
        const t = n > 0 && hi > lo ? (Math.log10(n) - lo) / (hi - lo) : 0;
        return gradColor(Math.min(1, Math.max(0, t)));
      },
    };
  }
  const counts = new Map();
  for (const v of all) counts.set(v, (counts.get(v) || 0) + 1);
  const keys = [...counts.keys()];
  return { numeric: false, counts, color: (v) => PALETTE[keys.indexOf(v) % PALETTE.length] };
}

function render({ model, el }) {
  const controller = new AbortController();
  const { signal } = controller;
  const style = document.createElement("style");
  style.textContent = CSS;
  const root = document.createElement("div");
  root.className = "pv";
  root.innerHTML = `
    <div class="pv-bar">
      <label>Colour by <select data-ref="colorBy"></select></label>
      <span data-ref="selInfo"></span>
    </div>
    <div class="pv-thumbs" data-ref="thumbs"></div>
    <div class="pv-main">
      <div data-ref="plate"></div>
      <div class="pv-side">
        <div class="pv-label">Legend</div>
        <div class="pv-legend" data-ref="legend"></div>
        <div class="pv-edit">
          <div class="pv-label">Edit selected wells</div>
          <select data-ref="editField"></select>
          <input data-ref="editValue" placeholder="value (suggests existing)">
          <datalist data-ref="valList"></datalist>
          <button data-ref="apply">Apply</button>
          <button data-ref="undo">Undo last edit</button>
        </div>
      </div>
    </div>
    <div class="pv-tip" data-ref="tip"></div>`;
  el.append(style, root);
  const $ = (name) => root.querySelector(`[data-ref="${name}"]`);
  const listId = `pv-vals-${Math.random().toString(36).slice(2)}`;
  $("valList").id = listId;
  $("editValue").setAttribute("list", listId);

  let selected = new Set(model.get("selection"));
  let cells = [];
  let scale = buildScale(model);
  let drag = null;

  function commitSelection() {
    model.set("selection", [...selected]);
    model.save_changes();
  }

  function paintSelection() {
    for (const { node, name, empty } of cells) {
      const on = selected.has(name);
      node.setAttribute("stroke", on ? "var(--pv-sel)" : empty ? "var(--pv-line)" : "none");
      node.setAttribute("stroke-width", on ? 2.5 : 1);
    }
    const n = selected.size;
    $("selInfo").textContent = `${n} well${n === 1 ? "" : "s"} selected on ${model.get("current_plate")}`;
    $("apply").textContent = `Apply to ${n} well${n === 1 ? "" : "s"}`;
    $("apply").disabled = n === 0;
  }

  function setSelection(next) {
    selected = next;
    paintSelection();
    commitSelection();
  }

  function fillSelect(select, options, value) {
    select.replaceChildren(...options.map((o) => new Option(o, o)));
    if (options.includes(value)) select.value = value;
  }

  function fillSuggestions() {
    const field = $("editField").value;
    const seen = new Set();
    for (const d of Object.values(model.get("detail"))) if (d[field]) seen.add(d[field]);
    if (field === model.get("color_field"))
      for (const p of model.get("plates")) for (const v of model.get("values")[p] || []) if (!isUnset(v)) seen.add(v);
    $("valList").replaceChildren(...[...seen].sort().map((v) => new Option(v)));
  }

  function drawPlate() {
    const plate = model.get("current_plate");
    if (!plate) {
      $("plate").innerHTML = `<div class="pv-empty">No wells to show. Load a template with assay conditions.</div>`;
      cells = [];
      return;
    }
    const [R, C] = dims(model.get("plate_format"));
    const vals = model.get("values")[plate] || [];
    const s = R === 16 ? 22 : 36;
    const pad = 24;
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("width", pad + C * s + 4);
    svg.setAttribute("height", pad + R * s + 4);
    const header = (x, y, text, wells) => {
      const t = document.createElementNS(NS, "text");
      t.setAttribute("x", x);
      t.setAttribute("y", y);
      t.setAttribute("text-anchor", "middle");
      t.setAttribute("class", "pv-hdr");
      t.textContent = text;
      t.addEventListener("click", (e) => {
        const next = e.shiftKey ? new Set(selected) : new Set();
        wells.forEach((w) => next.add(w));
        setSelection(next);
      });
      svg.append(t);
    };
    const allWells = [];
    for (let r = 0; r < R; r++) for (let c = 0; c < C; c++) allWells.push(wellName(r, c));
    header(10, 14, "all", allWells);
    for (let c = 0; c < C; c++) header(pad + c * s + s / 2, 14, c + 1, [...Array(R).keys()].map((r) => wellName(r, c)));
    for (let r = 0; r < R; r++) header(10, pad + r * s + s / 2 + 3, String.fromCharCode(65 + r), [...Array(C).keys()].map((c) => wellName(r, c)));
    const detail = model.get("detail");
    const tip = $("tip");
    cells = [];
    for (let r = 0; r < R; r++) {
      for (let c = 0; c < C; c++) {
        const name = wellName(r, c);
        const v = vals[r * C + c];
        const empty = isUnset(v);
        const node = document.createElementNS(NS, "circle");
        node.setAttribute("cx", pad + c * s + s / 2);
        node.setAttribute("cy", pad + r * s + s / 2);
        node.setAttribute("r", s / 2 - 2);
        node.setAttribute("fill", empty ? "var(--pv-unset)" : scale.color(v));
        if (empty) node.setAttribute("stroke-dasharray", "2 2");
        node.style.cursor = "pointer";
        node.addEventListener("mousedown", (e) => {
          drag = { r, c, base: e.shiftKey ? new Set(selected) : new Set() };
          selected = new Set([...drag.base, name]);
          paintSelection();
          e.preventDefault();
        });
        node.addEventListener("mouseenter", () => {
          const d = detail[name];
          const lines = d && Object.keys(d).length
            ? Object.entries(d).map(([k, x]) => `${k}: ${x}`).join("\n")
            : "(no metadata)";
          tip.textContent = `${plate} · ${name}\n${lines}`;
          tip.style.display = "block";
          if (drag) {
            const next = new Set(drag.base);
            for (let rr = Math.min(drag.r, r); rr <= Math.max(drag.r, r); rr++)
              for (let cc = Math.min(drag.c, c); cc <= Math.max(drag.c, c); cc++) next.add(wellName(rr, cc));
            selected = next;
            paintSelection();
          }
        });
        node.addEventListener("mousemove", (e) => {
          tip.style.left = `${e.clientX + 14}px`;
          tip.style.top = `${e.clientY + 14}px`;
        });
        node.addEventListener("mouseleave", () => { tip.style.display = "none"; });
        svg.append(node);
        cells.push({ node, name, value: v, empty });
      }
    }
    $("plate").replaceChildren(svg);
    paintSelection();
  }

  function drawLegend() {
    const legend = $("legend");
    const unsetRow = `<div class="pv-li" data-v=""><span class="pv-sw" style="background:var(--pv-unset);border:1px dashed var(--pv-line)"></span>unset</div>`;
    if (scale.numeric) {
      const stops = [0, 0.25, 0.5, 0.75, 1].map(gradColor).join(",");
      legend.innerHTML = `<div>${model.get("color_field")} (log scale)</div>
        <div class="pv-grad" style="background:linear-gradient(90deg,${stops})"></div>
        <div style="display:flex;justify-content:space-between"><span>${scale.lo}</span><span>${scale.hi}</span></div>${unsetRow}`;
    } else {
      const rows = [...scale.counts].sort((a, b) => b[1] - a[1]);
      legend.innerHTML = "";
      for (const [v, n] of rows) {
        const li = document.createElement("div");
        li.className = "pv-li";
        li.dataset.v = v;
        const sw = document.createElement("span");
        sw.className = "pv-sw";
        sw.style.background = scale.color(v);
        const label = document.createElement("span");
        label.textContent = v;
        const cnt = document.createElement("span");
        cnt.className = "pv-cnt";
        cnt.textContent = n;
        li.append(sw, label, cnt);
        legend.append(li);
      }
      legend.insertAdjacentHTML("beforeend", unsetRow);
    }
    for (const li of legend.querySelectorAll(".pv-li")) {
      const v = li.dataset.v;
      const match = (cell) => (v === "" ? cell.empty : !cell.empty && String(cell.value) === v);
      li.addEventListener("mouseenter", () => cells.forEach((cell) => { cell.node.style.opacity = match(cell) ? 1 : 0.15; }));
      li.addEventListener("mouseleave", () => cells.forEach((cell) => { cell.node.style.opacity = 1; }));
      li.addEventListener("click", (e) => {
        const next = e.shiftKey ? new Set(selected) : new Set();
        cells.forEach((cell) => { if (match(cell)) next.add(cell.name); });
        setSelection(next);
      });
    }
  }

  function drawThumbs() {
    const [R, C] = dims(model.get("plate_format"));
    const current = model.get("current_plate");
    const values = model.get("values");
    $("thumbs").replaceChildren(...model.get("plates").map((p) => {
      const canvas = document.createElement("canvas");
      const k = R === 16 ? 3 : 5;
      canvas.width = C * k;
      canvas.height = R * k;
      const ctx = canvas.getContext("2d");
      const pv = values[p] || [];
      for (let i = 0; i < R * C; i++) {
        ctx.fillStyle = isUnset(pv[i]) ? "#e8e8e8" : scale.color(pv[i]);
        ctx.fillRect((i % C) * k, Math.floor(i / C) * k, k - 0.5, k - 0.5);
      }
      const wrap = document.createElement("div");
      wrap.className = `pv-thumb${p === current ? " cur" : ""}`;
      wrap.title = p;
      wrap.append(canvas, p);
      wrap.addEventListener("click", () => {
        model.set("current_plate", p);
        model.save_changes();
      });
      return wrap;
    }));
  }

  function redraw() {
    scale = buildScale(model);
    fillSelect($("colorBy"), model.get("fields"), model.get("color_field"));
    const editField = $("editField").value || model.get("color_field");
    fillSelect($("editField"), model.get("fields"), editField);
    $("undo").disabled = !model.get("can_undo");
    drawThumbs();
    drawPlate();
    drawLegend();
    fillSuggestions();
  }

  function apply() {
    if (!selected.size) return;
    model.set("edit_request", {
      id: Date.now(),
      action: "set",
      plate: model.get("current_plate"),
      wells: [...selected],
      field: $("editField").value,
      value: $("editValue").value,
    });
    model.save_changes();
  }

  $("colorBy").addEventListener("change", (e) => {
    model.set("color_field", e.target.value);
    model.save_changes();
    $("editField").value = e.target.value;
  }, { signal });
  $("editField").addEventListener("change", fillSuggestions, { signal });
  $("apply").addEventListener("click", apply, { signal });
  $("editValue").addEventListener("keydown", (e) => { if (e.key === "Enter") apply(); }, { signal });
  $("undo").addEventListener("click", () => {
    model.set("edit_request", { id: Date.now(), action: "undo" });
    model.save_changes();
  }, { signal });
  window.addEventListener("mouseup", () => {
    if (drag) {
      drag = null;
      commitSelection();
    }
  }, { signal });
  root.tabIndex = 0;
  root.addEventListener("keydown", (e) => {
    if (e.key === "Escape") setSelection(new Set());
  }, { signal });

  for (const trait of ["values", "plates", "fields", "plate_format", "color_field", "current_plate", "can_undo"])
    model.on(`change:${trait}`, redraw);
  model.on("change:detail", () => { drawPlate(); fillSuggestions(); });
  model.on("change:selection", () => {
    selected = new Set(model.get("selection"));
    paintSelection();
  });
  redraw();
  return () => controller.abort();
}

export default { render };
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --extra dev --extra cli --extra app pytest tests/test_plate_viewer.py -v`
Expected: all PASS.

- [ ] **Step 6: Check the JS is packaged**

Run: `uv build --wheel -o /tmp/mihcsme-wheel && unzip -l /tmp/mihcsme-wheel/*.whl | grep plate_viewer`
Expected: both `mihcsme_py/widgets/plate_viewer.py` and `mihcsme_py/widgets/plate_viewer.js` listed. If the `.js` is missing, add to `[tool.uv.build-backend]` in `pyproject.toml`: `source-include = ["src/mihcsme_py/widgets/*.js"]` and rebuild.

- [ ] **Step 7: Commit**

```bash
git add src/mihcsme_py/widgets tests/test_plate_viewer.py
git commit -m "feat: add PlateViewer anywidget plate editor

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Generated metadata forms (`forms.py`)

**Files:**
- Create: `src/mihcsme_py/forms.py`
- Test: `tests/test_forms.py`

**Interfaces:**
- Produces:
  - `model_form(model_cls: type[BaseModel], instance: BaseModel | None = None, extra_items: int = 2) -> mo.ui.dictionary` — keys are field names; scalar → `mo.ui.text`/`mo.ui.text_area`, sub-model → nested `mo.ui.dictionary`, `List[sub-model]` → `mo.ui.array` of nested dictionaries (existing items + `extra_items` blanks).
  - `render_form(form: mo.ui.dictionary, model_cls: type[BaseModel]) -> object` — a marimo layout embedding the form's elements (labels from aliases, sub-models as accordion sections).
  - `form_to_model(model_cls: type[BaseModel], value: dict) -> tuple[BaseModel | None, str | None]` — `(model, None)` or `(None, error_message)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_forms.py`:

```python
"""Tests for generated Pydantic <-> marimo forms."""

import pytest

pytest.importorskip("marimo")

from mihcsme_py.forms import form_to_model, model_form  # noqa: E402
from mihcsme_py.models import (  # noqa: E402
    AssayInformation,
    Channel,
    DataCollaborator,
    DataOwner,
    InvestigationInformation,
    Specimen,
)


def test_form_prefills_scalar_and_nested_values():
    inv = InvestigationInformation(
        data_owner=DataOwner(first_name="Ada", last_name="Lovelace"),
        data_collaborators=[DataCollaborator(orcid="https://orcid.org/0000-0000-0000-0001")],
    )
    form = model_form(InvestigationInformation, inv)
    value = form.value
    assert value["data_owner"]["first_name"] == "Ada"
    assert value["data_owner"]["email"] == ""
    assert value["data_collaborators"][0]["orcid"] == "https://orcid.org/0000-0000-0000-0001"
    assert len(value["data_collaborators"]) == 3  # 1 existing + 2 blank


def test_form_without_instance_is_blank():
    value = model_form(InvestigationInformation).value
    assert value["data_owner"]["first_name"] == ""
    assert len(value["data_collaborators"]) == 2


def test_round_trip_unchanged():
    inv = InvestigationInformation(data_owner=DataOwner(first_name="Ada"))
    model, error = form_to_model(InvestigationInformation, model_form(InvestigationInformation, inv).value)
    assert error is None
    assert model.data_owner.first_name == "Ada"
    assert model.data_owner.email is None
    assert model.data_collaborators == []


def test_blank_list_items_are_dropped_and_nested_lists_work():
    spec = Specimen(channels=[Channel(entity="DNA", label="Nuclei", id="1")])
    info = AssayInformation(specimen=spec)
    model, error = form_to_model(AssayInformation, model_form(AssayInformation, info).value)
    assert error is None
    assert [c.entity for c in model.specimen.channels] == ["DNA"]


def test_whitespace_becomes_none():
    value = model_form(InvestigationInformation).value
    value["data_owner"]["first_name"] = "   "
    model, error = form_to_model(InvestigationInformation, value)
    assert error is None
    assert model.data_owner is None  # all-empty sub-model collapses to None


def test_form_to_model_returns_error_for_bad_orcid():
    value = model_form(InvestigationInformation).value
    value["data_owner"]["orcid"] = "0000-0001"
    model, error = form_to_model(InvestigationInformation, value)
    assert model is None
    assert "data_owner.orcid" in error
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --extra dev --extra cli --extra app pytest tests/test_forms.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mihcsme_py.forms'`.

- [ ] **Step 3: Implement `forms.py`**

Create `src/mihcsme_py/forms.py`:

```python
"""Build marimo forms from MIHCSME Pydantic models and read them back.

Requires marimo (``app`` extra) for :func:`model_form` and :func:`render_form`;
:func:`form_to_model` only needs pydantic.
"""

import inspect
from typing import Any, Dict, List, Optional, Tuple, Type, Union, get_args, get_origin

from pydantic import BaseModel, ValidationError

_LONG_TEXT_HINTS = ("description", "protocol", "conditions")


def _field_kind(annotation: Any) -> Tuple[str, Optional[Type[BaseModel]]]:
    """Classify a field annotation as ("scalar"|"model"|"list", sub_model)."""
    if get_origin(annotation) is Union:
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        return _field_kind(non_none[0]) if len(non_none) == 1 else ("scalar", None)
    if get_origin(annotation) in (list, List):
        inner = get_args(annotation)[0] if get_args(annotation) else None
        if inspect.isclass(inner) and issubclass(inner, BaseModel):
            return "list", inner
        return "scalar", None
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        return "model", annotation
    return "scalar", None


def _label(name: str, field: Any) -> str:
    return field.alias or name.replace("_", " ").capitalize()


def model_form(model_cls: Type[BaseModel], instance: Optional[BaseModel] = None, extra_items: int = 2):
    """Return a ``mo.ui.dictionary`` mirroring ``model_cls``, prefilled from ``instance``."""
    import marimo as mo

    elements: Dict[str, Any] = {}
    for name, field in model_cls.model_fields.items():
        current = getattr(instance, name, None) if instance is not None else None
        kind, sub = _field_kind(field.annotation)
        if kind == "model":
            elements[name] = model_form(sub, current, extra_items)
        elif kind == "list":
            items = list(current or [])
            forms = [model_form(sub, item, extra_items) for item in items]
            forms += [model_form(sub, None, extra_items) for _ in range(extra_items)]
            elements[name] = mo.ui.array(forms)
        else:
            widget = mo.ui.text_area if any(h in name for h in _LONG_TEXT_HINTS) else mo.ui.text
            elements[name] = widget(
                value="" if current is None else str(current),
                label=_label(name, field),
                placeholder=(field.description or "")[:80],
                full_width=True,
            )
    return mo.ui.dictionary(elements)


def render_form(form, model_cls: Type[BaseModel]):
    """Lay out a form from :func:`model_form`: scalars stacked, sub-models in accordions."""
    import marimo as mo

    scalars: List[Any] = []
    sections: Dict[str, Any] = {}
    for name, field in model_cls.model_fields.items():
        kind, sub = _field_kind(field.annotation)
        if kind == "model":
            sections[_label(name, field)] = render_form(form[name], sub)
        elif kind == "list":
            items = [
                mo.vstack([mo.md(f"**{sub.__name__} {i + 1}**"), render_form(item, sub)])
                for i, item in enumerate(form[name])
            ]
            sections[_label(name, field)] = mo.vstack(items)
        else:
            scalars.append(form[name])
    parts: List[Any] = list(scalars)
    if sections:
        parts.append(mo.accordion(sections, multiple=True))
    return mo.vstack(parts, gap=0.5)


def _form_data(model_cls: Type[BaseModel], value: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert form values to model data; ``None`` if every field is empty."""
    data: Dict[str, Any] = {}
    for name, field in model_cls.model_fields.items():
        kind, sub = _field_kind(field.annotation)
        raw = value.get(name)
        if kind == "model":
            data[name] = _form_data(sub, raw or {})
        elif kind == "list":
            items = [_form_data(sub, item or {}) for item in (raw or [])]
            data[name] = [item for item in items if item is not None]
        else:
            text = "" if raw is None else str(raw).strip()
            data[name] = text or None
    if all(v is None or v == [] for v in data.values()):
        return None
    return data


def form_to_model(
    model_cls: Type[BaseModel], value: Dict[str, Any]
) -> Tuple[Optional[BaseModel], Optional[str]]:
    """Validate form values into ``model_cls``; return ``(model, None)`` or ``(None, error)``."""
    data = _form_data(model_cls, value) or {}
    try:
        return model_cls.model_validate(data), None
    except ValidationError as e:
        messages = [
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()
        ]
        return None, "\n".join(messages)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --extra dev --extra cli --extra app pytest tests/test_forms.py -v`
Expected: all PASS. If `test_form_to_model_returns_error_for_bad_orcid` fails because `OrcidUrl` accepts the value, check `_validate_orcid` in `models.py:36` and use a value it rejects (e.g. `"not-an-orcid"`).

- [ ] **Step 5: Commit**

```bash
git add src/mihcsme_py/forms.py tests/test_forms.py
git commit -m "feat: generate marimo metadata forms from pydantic models

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Flagship app — move, header, example data, plate editor tab

**Files:**
- Move: `examples/marimo/marimo_omero_app.py` → `examples/marimo/mihcsme_app.py`
- Create: `src/mihcsme_py/templates/MIHCSME_example.xlsx` (copy of `MIHCSME Template_example.xlsx`)
- Modify: `examples/marimo/mihcsme_app.py`

**Interfaces:**
- Consumes: `PlateViewer.set_data/on_change` (Task 3).
- Produces (notebook globals used by Tasks 6–7): `get_wells`, `set_wells` (mo.state of the well dataframe), `plate_viewer`, `wells_tab_content`. Remove globals `df`, `editor`, `column_select`, `plate_select`, `format_select`, `visualize_plate`. `metadata_updated` keeps existing meaning (defined in Task 6; in this task keep it as `metadata.update_conditions_from_dataframe(get_wells())`).

- [ ] **Step 1: Move the file and bundle example data**

```bash
git mv examples/marimo/marimo_omero_app.py examples/marimo/mihcsme_app.py
cp "MIHCSME Template_example.xlsx" src/mihcsme_py/templates/MIHCSME_example.xlsx
```

- [ ] **Step 2: Fix the script header**

Replace the `# /// script` block at the top of `examples/marimo/mihcsme_app.py` with:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "llm==0.28",
#     "llm-openrouter==0.5",
#     "marimo>=0.19.6",
#     "mihcsme-py[app,omero]",
#     "zeroc-ice",
# ]
#
# [tool.uv.sources]
# zeroc-ice = { url = "https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases/download/20240202/zeroc_ice-3.6.5-cp312-cp312-manylinux_2_28_x86_64.whl" }
# mihcsme-py = { git = "https://github.com/Leiden-Cell-Observatory/MIHCSME-py.git", rev = "main" }
# ///
```

- [ ] **Step 3: Default to the bundled example**

In the imports cell (the one with `import marimo as mo`), add these lines and return `EXAMPLE_FILE`:

```python
    from importlib.resources import files as _resource_files

    EXAMPLE_FILE = str(_resource_files("mihcsme_py") / "templates" / "MIHCSME_example.xlsx")
```

In the cell that creates `path_input` (`if file_source.value == "File Path":`), change the text input to:

```python
        path_input = mo.ui.text(
            value=EXAMPLE_FILE,
            label="Excel file path (pre-filled with the bundled example):",
            full_width=True,
        )
```

- [ ] **Step 4: Replace the wells tab cells**

Delete these cells entirely: the `visualize_plate` function cell (starts `def visualize_plate(df, column_to_display`), the `df = metadata.to_dataframe()` cell, the controls cell (`column_select = mo.ui.dropdown(`), the `editor = mo.ui.data_editor(df)` cell, the `metadata_updated = metadata.update_conditions_from_dataframe(editor.value)` cell and the `wells_tab_content` cell. Also add `from mihcsme_py.widgets import PlateViewer` to the imports cell.

Add these cells in their place:

```python
@app.cell
def _(metadata, mo, pd):
    # Well dataframe is app state: plate editor and table both write to it
    get_wells, set_wells = mo.state(
        metadata.to_dataframe() if metadata is not None else pd.DataFrame()
    )
    return get_wells, set_wells


@app.cell
def _(PlateViewer, metadata, set_wells):
    # Created once per loaded template; edits flow back via on_change -> set_wells
    plate_viewer = PlateViewer()
    plate_viewer.on_change(set_wells)
    _ = metadata
    return (plate_viewer,)


@app.cell
def _(get_wells, plate_viewer):
    # Push data to the widget; does not depend on the selection (performance rule)
    plate_viewer.set_data(get_wells())
    return


@app.cell
def _(mo, plate_viewer):
    plate_viewer_ui = mo.ui.anywidget(plate_viewer)
    return (plate_viewer_ui,)


@app.cell
def _(get_wells, mo, set_wells):
    wells_table = mo.ui.data_editor(get_wells(), on_change=set_wells)
    return (wells_table,)


@app.cell
def _(get_wells, metadata):
    metadata_updated = (
        metadata.update_conditions_from_dataframe(get_wells()) if metadata is not None else None
    )
    return (metadata_updated,)


@app.cell(hide_code=True)
def _(metadata, mo, plate_viewer_ui, wells_table):
    if metadata is None:
        wells_tab_content = mo.callout(
            mo.md("**Please load a template first** in the Load Template tab."), kind="warn"
        )
    else:
        wells_tab_content = mo.vstack(
            [
                mo.md(
                    """
                    ### Plate layout

                    Check your design at a glance. Select wells (drag, row/column headers,
                    legend entries; Shift adds, Esc clears), then set a value in the edit panel.
                    """
                ),
                plate_viewer_ui,
                mo.accordion({"Table view (bulk edit / copy-paste)": wells_table}),
            ],
            gap=2,
        )
    return (wells_tab_content,)
```

- [ ] **Step 5: Fix references and check the notebook**

Run: `grep -n "editor\.\|df_updated\|\bdf\b\|column_select\|plate_select\|format_select" examples/marimo/mihcsme_app.py`
Expected: no remaining uses outside deleted cells. Any remaining cell that used `df` for display should use `get_wells()` instead; `df_updated` → `get_wells()`.

Run: `uvx marimo check --fix examples/marimo/mihcsme_app.py`
Expected: no errors (warnings about unused variables are acceptable only if they pre-existed).

- [ ] **Step 6: Run the app and verify by hand**

Run: `uv run --extra app --extra llm marimo run examples/marimo/mihcsme_app.py --port 2718`
Expected: app opens, example loads, Edit Wells tab shows the plate editor with 72 wells coloured by Treatment; selecting wells and applying a value updates the plate and the table view; Undo restores it. Stop the server (Ctrl-C).

- [ ] **Step 7: Commit**

```bash
git add examples/marimo/mihcsme_app.py src/mihcsme_py/templates/MIHCSME_example.xlsx
git commit -m "feat(app): flagship mihcsme_app with plate editor and bundled example

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Flagship app — generated metadata forms

**Files:**
- Modify: `examples/marimo/mihcsme_app.py`

**Interfaces:**
- Consumes: `model_form`, `render_form`, `form_to_model` (Task 4); `get_wells` (Task 5).
- Produces: `investigation_form`, `study_form`, `assay_form` (mo.ui.dictionary), `metadata_updated` (MIHCSMEMetadata with edited wells **and** sections — used by Export and OMERO upload), `metadata_tab_content`.

- [ ] **Step 1: Delete the hand-written form cells**

Delete: the `create_pydantic_form` function cell; the Investigation form cell (`inv_data_owner_fields`…), the cell that builds `inv_updated_*`; the Study form cell (`study_fields = create_pydantic_form`…) and `study_updated_*` cell; the Assay form cell (`assay_fields`…, `specimen_channel_dicts`) and the `assay_updated_*` cell; the `metadata_tab_content` cell; and the Task 5 `metadata_updated` cell (replaced below). Add to imports cell: `from mihcsme_py.forms import form_to_model, model_form, render_form`.

- [ ] **Step 2: Add the new form cells**

```python
@app.cell
def _(AssayInformation, InvestigationInformation, StudyInformation, metadata, model_form):
    investigation_form = model_form(
        InvestigationInformation, metadata.investigation_information if metadata else None
    )
    study_form = model_form(StudyInformation, metadata.study_information if metadata else None)
    assay_form = model_form(AssayInformation, metadata.assay_information if metadata else None)
    return assay_form, investigation_form, study_form


@app.cell
def _(
    AssayInformation,
    InvestigationInformation,
    StudyInformation,
    assay_form,
    form_to_model,
    get_wells,
    investigation_form,
    metadata,
    study_form,
):
    # Combine edited wells and edited sections; invalid sections keep the loaded values
    form_errors = {}
    metadata_updated = None
    if metadata is not None:
        _sections = {}
        for _key, _cls, _form in [
            ("investigation_information", InvestigationInformation, investigation_form),
            ("study_information", StudyInformation, study_form),
            ("assay_information", AssayInformation, assay_form),
        ]:
            _model, _error = form_to_model(_cls, _form.value)
            if _error:
                form_errors[_key] = _error
            else:
                _sections[_key] = _model
        metadata_updated = metadata.update_conditions_from_dataframe(get_wells()).model_copy(
            update=_sections
        )
    return form_errors, metadata_updated


@app.cell(hide_code=True)
def _(
    AssayInformation,
    InvestigationInformation,
    StudyInformation,
    assay_form,
    form_errors,
    investigation_form,
    metadata,
    mo,
    render_form,
    study_form,
):
    def _section(key, form, cls):
        _error = form_errors.get(key)
        _parts = [render_form(form, cls)]
        if _error:
            _parts.insert(0, mo.callout(mo.md(f"**Not saved — fix these fields:**\n\n```\n{_error}\n```"), kind="danger"))
        return mo.vstack(_parts)

    if metadata is None:
        metadata_tab_content = mo.callout(
            mo.md("**Please load a template first** in the Load Template tab."), kind="warn"
        )
    else:
        metadata_tab_content = mo.vstack(
            [
                mo.md("### Metadata\n\nChanges are applied as you type and used by Export and OMERO upload."),
                mo.ui.tabs(
                    {
                        "Investigation": _section("investigation_information", investigation_form, InvestigationInformation),
                        "Study": _section("study_information", study_form, StudyInformation),
                        "Assay": _section("assay_information", assay_form, AssayInformation),
                    }
                ),
            ],
            gap=2,
        )
    return (metadata_tab_content,)
```

- [ ] **Step 3: Simplify the export cell**

In the export cell (the one with `if export_button.value:`), replace its parameter-dependent body so it writes `metadata_updated` directly. Replace from `_final_metadata = metadata_updated.model_copy(deep=True)` through the `except NameError: pass` block with:

```python
            _final_metadata = metadata_updated
```

Remove the now-unused `inv_updated_*`, `study_updated_*`, `assay_updated_*`, `InvestigationInformation`, `StudyInformation`, `AssayInformation` references from that cell (marimo will drop them from the signature).

- [ ] **Step 4: Check and verify**

Run: `grep -n "inv_updated\|study_updated\|assay_updated\|create_pydantic_form\|_fields\[" examples/marimo/mihcsme_app.py`
Expected: no matches.

Run: `uvx marimo check --fix examples/marimo/mihcsme_app.py`
Expected: no errors.

Run: `uv run --extra app --extra llm marimo run examples/marimo/mihcsme_app.py --port 2718`
Expected: Edit Metadata tab shows three tabs with prefilled values from the example; typing `bad` into Data owner → ORCID shows a red "Not saved" callout naming `data_owner.orcid`; clearing it removes the callout; Export produces an xlsx containing the edited Study title. Stop the server.

- [ ] **Step 5: Commit**

```bash
git add examples/marimo/mihcsme_app.py
git commit -m "feat(app): generated metadata forms with inline validation

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Flagship app — OMERO status table and offline mode

**Files:**
- Modify: `examples/marimo/mihcsme_app.py`

**Interfaces:**
- Consumes: `plate_ops.plate_status` and `omero_plates` key (Task 2); `get_wells` (Task 5); `metadata_updated` (Task 6).
- Produces: `OMERO_AVAILABLE: bool`, `omero_validate_display` (now includes the status table).

- [ ] **Step 1: Make OMERO imports optional**

In the imports cell, replace the OMERO-dependent imports:

```python
    from mihcsme_py.omero_connection import connect as omero_connect
```

with:

```python
    try:
        import omero  # noqa: F401
        from mihcsme_py.omero_connection import connect as omero_connect

        OMERO_AVAILABLE = True
    except ImportError:
        omero_connect = None
        OMERO_AVAILABLE = False
```

and return `OMERO_AVAILABLE`. Add `from mihcsme_py.plate_ops import plate_status`.

- [ ] **Step 2: Add the status table to validation**

In the validation cell (`omero_validate_display = mo.md("")`), after `_validation = validate_metadata_against_omero(...)` and after the callout is built, wrap the result together with the table:

```python
                _status_table = mo.ui.table(
                    plate_status(get_wells(), _validation),
                    selection=None,
                    label="Per-plate status",
                )
                omero_validate_display = mo.vstack([omero_validate_display, _status_table])
```

Place these lines at the end of the `try:` block, so all three callout branches get the table.

- [ ] **Step 3: Gate the OMERO tab**

In the main tabs cell (`main_tabs = mo.ui.tabs(`), replace `"5. OMERO": omero_tab_content,` with:

```python
            "5. OMERO": omero_tab_content
            if OMERO_AVAILABLE
            else mo.callout(
                mo.md(
                    "OMERO support is not installed. Install it with "
                    "`pip install 'mihcsme-py[omero]'` (needs the zeroc-ice wheel). "
                    "All other tabs work offline."
                ),
                kind="info",
            ),
```

- [ ] **Step 4: Check and verify**

Run: `uvx marimo check --fix examples/marimo/mihcsme_app.py`
Expected: no errors.

Run (without omero installed): `uv run --extra app --extra llm marimo run examples/marimo/mihcsme_app.py --port 2718`
Expected: app loads, OMERO tab shows the install hint, all other tabs work. Stop the server.

If an OMERO server is available: connect, validate against a Screen → callout plus "Per-plate status" table with one row per plate.

- [ ] **Step 5: Commit**

```bash
git add examples/marimo/mihcsme_app.py
git commit -m "feat(app): per-plate OMERO status table and offline mode

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Examples cleanup and three short notebooks

**Files:**
- Delete: `examples/marimo/marimo_template_app.py`, `examples/marimo/marimo_omero_example.py`, `examples/marimo/mihcsme_omero_upload.py`, `examples/marimo/mihcsme_llm.py` (replaced by 03)
- Delete (untracked, from disk): `examples/marimo_omero_app.py` (empty), `examples/marimo/__marimo__/`, `examples/marimo/__pycache__/`, `examples/__marimo__/`, `examples/marimo/LEI-MIHCSME_migration_data_merged.xlsx`
- Create: `examples/marimo/01_parse_and_explore.py`, `examples/marimo/02_omero_roundtrip.py`, `examples/marimo/03_llm_fill.py`
- Modify: `examples/marimo/Dockerfile`, `examples/marimo/requirements.txt`, `examples/marimo/DOCKER_DEPLOYMENT.md`, `README.md`

- [ ] **Step 1: Remove old files**

```bash
git rm examples/marimo/marimo_template_app.py examples/marimo/marimo_omero_example.py examples/marimo/mihcsme_omero_upload.py examples/marimo/mihcsme_llm.py
rm -f examples/marimo_omero_app.py examples/marimo/LEI-MIHCSME_migration_data_merged.xlsx
rm -rf examples/marimo/__marimo__ examples/marimo/__pycache__ examples/__marimo__
```

Do **not** touch `examples/marimo/marimo_bia.py`.

- [ ] **Step 2: Create `01_parse_and_explore.py`**

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["marimo>=0.19.6", "mihcsme-py"]
#
# [tool.uv.sources]
# mihcsme-py = { git = "https://github.com/Leiden-Cell-Observatory/MIHCSME-py.git", rev = "main" }
# ///

import marimo

__generated_with = "0.19.6"
app = marimo.App(width="medium")


@app.cell
def _():
    import io
    from importlib.resources import files

    import marimo as mo

    from mihcsme_py import fill_template, parse_excel_to_model, write_metadata_to_excel
    return fill_template, files, io, mo, parse_excel_to_model, write_metadata_to_excel


@app.cell
def _(mo):
    mo.md("""
    # Parse and explore a MIHCSME file

    Load a MIHCSME Excel file into a validated Pydantic model, look at the
    well conditions as a table and write it back to Excel.
    """)
    return


@app.cell
def _(files, parse_excel_to_model):
    example_path = files("mihcsme_py") / "templates" / "MIHCSME_example.xlsx"
    metadata = parse_excel_to_model(str(example_path))
    metadata.investigation_information
    return (metadata,)


@app.cell
def _(metadata):
    metadata.study_information
    return


@app.cell
def _(metadata):
    wells = metadata.to_dataframe()
    wells
    return (wells,)


@app.cell
def _(wells):
    wells.groupby("Plate").size().rename("wells per plate")
    return


@app.cell
def _(io, metadata, mo, write_metadata_to_excel):
    _buffer = io.BytesIO()
    write_metadata_to_excel(metadata, _buffer)
    mo.download(_buffer.getvalue(), filename="metadata_export.xlsx", label="Download as Excel")
    return


@app.cell
def _(fill_template, io, metadata, mo):
    _buffer = io.BytesIO()
    fill_template(metadata, _buffer)
    mo.download(_buffer.getvalue(), filename="LEI-MIHCSME_filled.xlsx", label="Download filled LEI template")
    return


if __name__ == "__main__":
    app.run()
```

Before writing this, run `uv run python -c "import inspect, mihcsme_py; print(inspect.signature(mihcsme_py.fill_template))"` and adapt the `fill_template(...)` call to its actual signature (it must accept an output target; if it only accepts a path, write to a temp file and read its bytes).

- [ ] **Step 3: Create `02_omero_roundtrip.py`**

```python
# /// script
# requires-python = ">=3.12"
# dependencies = ["marimo>=0.19.6", "mihcsme-py[omero]", "zeroc-ice"]
#
# [tool.uv.sources]
# zeroc-ice = { url = "https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases/download/20240202/zeroc_ice-3.6.5-cp312-cp312-manylinux_2_28_x86_64.whl" }
# mihcsme-py = { git = "https://github.com/Leiden-Cell-Observatory/MIHCSME-py.git", rev = "main" }
# ///

import marimo

__generated_with = "0.19.6"
app = marimo.App(width="medium")


@app.cell
def _():
    from importlib.resources import files

    import marimo as mo

    from mihcsme_py import (
        download_metadata_from_omero,
        parse_excel_to_model,
        upload_metadata_to_omero,
        validate_metadata_against_omero,
    )
    from mihcsme_py.omero_connection import connect
    from mihcsme_py.plate_ops import plate_status
    return (
        connect,
        download_metadata_from_omero,
        files,
        mo,
        parse_excel_to_model,
        plate_status,
        upload_metadata_to_omero,
        validate_metadata_against_omero,
    )


@app.cell
def _(mo):
    mo.md("""
    # OMERO round-trip

    Validate a MIHCSME file against an OMERO Screen, upload it, download it
    again and compare. Credentials are typed below and never stored.
    """)
    return


@app.cell
def _(mo):
    login = mo.ui.dictionary(
        {
            "host": mo.ui.text(value="localhost", label="Host"),
            "user": mo.ui.text(label="User"),
            "password": mo.ui.text(kind="password", label="Password"),
            "group": mo.ui.text(label="Group (optional)"),
            "screen_id": mo.ui.number(start=1, step=1, label="Screen ID"),
        }
    ).form(submit_button_label="Connect and validate")
    login
    return (login,)


@app.cell
def _(files, parse_excel_to_model):
    metadata = parse_excel_to_model(
        str(files("mihcsme_py") / "templates" / "MIHCSME_example.xlsx")
    )
    return (metadata,)


@app.cell
def _(connect, login, mo):
    mo.stop(login.value is None, mo.md("Fill in the form to connect."))
    conn = connect(
        host=login.value["host"],
        user=login.value["user"],
        password=login.value["password"],
        group=login.value["group"] or None,
    )
    screen_id = int(login.value["screen_id"])
    return conn, screen_id


@app.cell
def _(conn, metadata, plate_status, screen_id, validate_metadata_against_omero):
    validation = validate_metadata_against_omero(conn, metadata, "Screen", screen_id)
    plate_status(metadata.to_dataframe(), validation)
    return (validation,)


@app.cell
def _(mo, validation):
    upload_button = mo.ui.run_button(label="Upload to OMERO", disabled=not validation["valid"])
    upload_button
    return (upload_button,)


@app.cell
def _(conn, metadata, mo, screen_id, upload_button, upload_metadata_to_omero):
    mo.stop(not upload_button.value)
    upload_result = upload_metadata_to_omero(conn, metadata, "Screen", screen_id)
    upload_result
    return


@app.cell
def _(conn, download_metadata_from_omero, metadata, screen_id):
    downloaded = download_metadata_from_omero(conn, "Screen", screen_id)
    same_wells = downloaded.to_dataframe().shape == metadata.to_dataframe().shape
    {"wells match": same_wells, "downloaded wells": len(downloaded.assay_conditions)}
    return


if __name__ == "__main__":
    app.run()
```

Before writing, check the real signatures: `uv run python -c "import inspect; from mihcsme_py import upload_metadata_to_omero as u, download_metadata_from_omero as d; from mihcsme_py.omero_connection import connect as c; print(inspect.signature(u)); print(inspect.signature(d)); print(inspect.signature(c))"` and adapt keyword names in the calls above to match.

- [ ] **Step 4: Create `03_llm_fill.py`**

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["marimo>=0.19.6", "mihcsme-py[llm]", "llm-openrouter"]
#
# [tool.uv.sources]
# mihcsme-py = { git = "https://github.com/Leiden-Cell-Observatory/MIHCSME-py.git", rev = "main" }
# ///

import marimo

__generated_with = "0.19.6"
app = marimo.App(width="medium")


@app.cell
def _():
    import llm
    import marimo as mo

    from mihcsme_py import MIHCSMEMetadataLLM
    return MIHCSMEMetadataLLM, llm, mo


@app.cell
def _(mo):
    mo.md("""
    # Fill MIHCSME metadata from lab notes with an LLM

    Paste notes, pick a model (configured via the `llm` CLI, e.g.
    `llm keys set openrouter`) and get structured Investigation / Study /
    Assay information back. Well conditions are not generated.
    """)
    return


@app.cell
def _(llm, mo):
    notes = mo.ui.text_area(
        placeholder="We imaged HeLa cells treated with DMSO or 10 µM compound X on an Opera Phenix, 40x, 4 channels ...",
        full_width=True,
        rows=8,
    )
    model_choice = mo.ui.dropdown(
        options=[m.model_id for m in llm.get_models()], label="Model"
    )
    run = mo.ui.run_button(label="Extract metadata")
    mo.vstack([notes, model_choice, run])
    return model_choice, notes, run


@app.cell
def _(MIHCSMEMetadataLLM, llm, mo, model_choice, notes, run):
    mo.stop(not run.value or not notes.value or not model_choice.value)
    _response = llm.get_model(model_choice.value).prompt(
        f"Extract MIHCSME metadata from these lab notes. Leave unknown fields empty.\n\n{notes.value}",
        schema=MIHCSMEMetadataLLM,
    )
    extracted = MIHCSMEMetadataLLM.model_validate_json(_response.text())
    extracted
    return


if __name__ == "__main__":
    app.run()
```

- [ ] **Step 5: Update Docker, requirements, docs, README**

`examples/marimo/requirements.txt` — replace the mihcsme-py line with:

```
mihcsme-py[app,omero] @ git+https://github.com/Leiden-Cell-Observatory/MIHCSME-py.git@main
```

`examples/marimo/Dockerfile` — replace `COPY --link marimo_omero_app.py .` with `COPY --link mihcsme_app.py .` and in `CMD` replace `marimo_omero_app.py` with `mihcsme_app.py`.

`examples/marimo/DOCKER_DEPLOYMENT.md` — replace every `marimo_omero_app.py` with `mihcsme_app.py` (`sed -i 's/marimo_omero_app\.py/mihcsme_app.py/g' examples/marimo/DOCKER_DEPLOYMENT.md`).

`README.md` — line 5 badge URL: replace `examples/marimo/marimo_omero_app.py` with `examples/marimo/mihcsme_app.py`. After the "Quick Start" section's Python API subsection, add:

```markdown
### Examples

| Notebook | What it shows |
|---|---|
| [`examples/marimo/mihcsme_app.py`](examples/marimo/mihcsme_app.py) | Flagship app: load Excel, plate editor, metadata forms, export, OMERO validate/upload with per-plate status |
| [`examples/marimo/01_parse_and_explore.py`](examples/marimo/01_parse_and_explore.py) | Excel → validated model → well table → Excel / filled template |
| [`examples/marimo/02_omero_roundtrip.py`](examples/marimo/02_omero_roundtrip.py) | Validate, upload and download metadata on an OMERO Screen |
| [`examples/marimo/03_llm_fill.py`](examples/marimo/03_llm_fill.py) | Fill Investigation/Study/Assay information from lab notes with an LLM |

Run the app locally: `uvx marimo run --sandbox examples/marimo/mihcsme_app.py`
```

- [ ] **Step 6: Check all notebooks**

Run: `uvx marimo check --fix examples/marimo/*.py`
Expected: no errors for `mihcsme_app.py`, `01_*`, `02_*`, `03_*` (ignore `marimo_bia.py`).

Run: `uv run --extra app marimo export html examples/marimo/01_parse_and_explore.py -o /tmp/01.html`
Expected: exit code 0 (notebook runs end to end).

Run: `grep -rn "marimo_omero_app\|marimo_template_app" --exclude-dir=.git --exclude-dir=.venv --exclude-dir=docs/superpowers .`
Expected: no matches.

- [ ] **Step 7: Commit**

```bash
git add examples/marimo/01_parse_and_explore.py examples/marimo/02_omero_roundtrip.py examples/marimo/03_llm_fill.py examples/marimo/Dockerfile examples/marimo/requirements.txt examples/marimo/DOCKER_DEPLOYMENT.md README.md
git status --short examples/  # verify marimo_bia.py is NOT staged
git commit -m "docs(examples): one flagship app plus three short example notebooks

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Browser smoke test

**Files:**
- Create: `tests/test_app_smoke.py`
- Modify: `pyproject.toml` (`dev` extra: add `playwright>=1.40`)

**Interfaces:**
- Consumes: `examples/marimo/mihcsme_app.py` with default example loading (Task 5).

- [ ] **Step 1: Write the smoke test**

Add `"playwright>=1.40",` to the `dev` extra in `pyproject.toml`, run `uv lock`.

Create `tests/test_app_smoke.py`:

```python
"""Headless smoke test: the flagship app loads the example and renders the plate editor."""

import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
pytest.importorskip("anywidget")

APP = Path(__file__).parents[1] / "examples" / "marimo" / "mihcsme_app.py"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def app_url():
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "marimo", "run", str(APP), "--headless", "--no-token",
         "--port", str(port), "--no-sandbox"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            break
        except OSError:
            time.sleep(0.5)
    yield url
    proc.terminate()
    proc.wait(timeout=10)


@pytest.mark.slow
def test_plate_editor_renders(app_url):
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:  # browser binaries not installed
            pytest.skip(f"Chromium not available: {e}")
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(app_url)
        page.get_by_text("2. Edit Wells").click(timeout=60000)
        circles = page.locator(".pv svg circle")
        circles.first.wait_for(timeout=60000)
        assert circles.count() in (96, 384)
        assert errors == []
        browser.close()
```

- [ ] **Step 2: Run it**

Run: `uv run --extra dev --extra cli --extra app --extra llm playwright install chromium && uv run --extra dev --extra cli --extra app --extra llm pytest tests/test_app_smoke.py -v -m slow`
Expected: PASS. If the tab label differs, match the label used in `main_tabs` in `mihcsme_app.py`.

- [ ] **Step 3: Full suite**

Run: `uv run --extra dev --extra cli --extra app pytest tests/ -v -m "not slow"`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_app_smoke.py pyproject.toml uv.lock
git commit -m "test: headless smoke test for the flagship app plate editor

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
