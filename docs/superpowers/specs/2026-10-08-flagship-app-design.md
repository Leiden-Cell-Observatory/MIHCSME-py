# Flagship marimo app — design

Date: 2026-10-08
Status: approved in conversation, pending written-spec review

## Goal

Make the existing MIHCSME OMERO marimo app better and make it the single flagship app. Keep it simple: the main goal is improving the current app, not building a new platform.

Users are wet-lab scientists. Typical data: 1–50 plates, 96- or 384-well (up to ~20k wells). Typical flow:

1. Load a MIHCSME Excel (AssayConditions sheet, one row per well).
2. Check the plate design visually and make small edits.
3. Fill in Investigation / Study / Assay information.
4. Match against an OMERO Screen/Plate after acquisition, upload, see per-plate status.

The app doubles as a proof of concept that a plate design can be carried into OMERO cleanly.

## Out of scope (next round)

- Plate-map grid importer (rows A–P × cols 1–24 per sheet)
- Analysis results / heatmaps of readouts, QC (Z′)
- Design-first registration in OMERO before acquisition, OMERO → app round-trip
- marimo-studio views
- Rule-based layout generation, 1536-well plates, zoom, keyboard well navigation

## 1. File layout

```
src/mihcsme_py/
  plate_ops.py              NEW  pure dataframe functions for the editor
  widgets/
    __init__.py             NEW  exports PlateViewer; clear ImportError hint without anywidget
    plate_viewer.py         NEW  anywidget class + traitlets
    plate_viewer.js         NEW  ESM frontend, loaded from file
examples/marimo/
  mihcsme_app.py            NEW  flagship (replaces marimo_omero_app.py + marimo_template_app.py)
  01_parse_and_explore.py   NEW  Excel -> model -> validate -> dataframe -> write Excel/template
  02_omero_roundtrip.py     NEW  connect (UI inputs, no hard-coded credentials), upload, download, compare
  03_llm_fill.py            NEW  from mihcsme_llm.py: notes -> LLM -> MIHCSMEMetadata
  Dockerfile, DOCKER_DEPLOYMENT.md, requirements.txt   point to mihcsme_app.py
```

- `pyproject.toml`: new optional extra `app = ["anywidget", "marimo"]`. Core dependencies unchanged.
- Flagship script header depends on `mihcsme-py[app,omero]` from git `main` (fixes the dead `rev = "marimo_app"` pin). LLM packages optional; the LLM panel only shows when `llm` imports.
- Deleted: `marimo_omero_app.py`, `marimo_template_app.py`, `marimo_omero_example.py`, `mihcsme_omero_upload.py`, empty top-level `examples/marimo_omero_app.py`, `examples/marimo/__marimo__/`, `__pycache__/`, xlsx files under `examples/`.
- Sample data: the bundled LEI template has no wells, so a copy of `MIHCSME Template_example.xlsx` is bundled as `mihcsme_py/templates/MIHCSME_example.xlsx`; the app pre-fills it as the default file and `01` uses it.
- Untouched: `examples/jupyter`, `examples/R`, untracked `examples/marimo/marimo_bia.py` (unrelated, contains credentials — must never be committed).
- README: molab badge -> `examples/marimo/mihcsme_app.py`; short examples table.

## 2. Plate editor (`PlateViewer` anywidget)

Purpose: check-and-tweak. Opening it answers "is my design what I think it is?" at a glance. Look and feel follows the clickable mockup reviewed in brainstorming (`.superpowers/brainstorm/*/content/plate-viewer.html`); final tuning happens with the user once running in the real app.

Traitlets, Python -> JS (re-sent only when data or colour field changes):

| trait | type | content |
|---|---|---|
| `plates` | list[str] | plate names |
| `plate_format` | "96" / "384" | from `detect_format`, user can override |
| `fields` | list[str] | condition columns |
| `color_field` | str | field driving colours |
| `values` | dict[str, list] | plate -> row-major list of `color_field` values |
| `detail` | dict[str, dict] | well -> all fields, current plate only (tooltip) |

JS -> Python:

| trait | content |
|---|---|
| `current_plate` | selected plate |
| `selection` | list of well names |
| `edit_request` | `{id, plate, wells, field, value}`; set on Apply, consumed by Python |

UI:

- Plate thumbnails (canvas) to switch plate; current plate outlined.
- SVG grid; click a well, drag a rectangle, click row/column header, "all" corner; Shift adds; Esc clears.
- Hover tooltip with all fields of the well.
- Legend with value counts; hover highlights matching wells, click selects them; "unset" entry.
- Edit panel: field dropdown, value input with suggestions from existing values, "Apply to N wells" (Enter applies), Undo.
- Colours: 20-colour categorical palette (wraps; legend hover disambiguates). Field ≥ 90 % numeric -> sequential log-scale gradient with min/max legend. Unset wells: background fill with dashed outline. Follows marimo light/dark theme.

Performance rule (from spike: 20 × 384 wells renders in ~20 ms, ~100 KB payload; ~300 ms round-trips were mostly cell re-runs): cells that push data to the widget must not depend on `selection`; only cells that need the selection read it.

Undo: Python keeps one previous dataframe; Undo restores it.

The raw well table (`mo.ui.data_editor`) stays, in a collapsed "Table view" accordion under the editor, for bulk copy-paste.

## 3. `plate_ops.py`

Pure functions on the well dataframe (columns `Plate`, `Well`, condition fields):

- `apply_edit(df, plate, wells, field, value) -> DataFrame` — returns a new dataframe; adds the column if `field` is new; ignores wells not in `df` for that plate.
- `detect_format(wells) -> Literal["96", "384"]` — "384" if any row > H or column > 12.
- `widget_payload(df, color_field, plate_format) -> dict` — builds `plates`, `values` (row-major, missing wells -> `None`) and `fields`; `detail_payload(df, plate)` builds `detail`.

Well names are normalised the same way as `AssayCondition` (e.g. `A1` -> `A01`).

## 4. Metadata forms

Keep the Investigation / Study / Assay tabs. Replace hand-written field cells with one helper, `model_form(model_cls, instance) -> mo.ui.dictionary`, that builds text inputs from Pydantic field names/descriptions and returns updated values. Validation errors from Pydantic show inline under the form (`mo.callout`, kind `danger`). Nested sections (e.g. DataOwner) become one form group each.

## 5. OMERO tab

- Same flow as today: connect, choose Screen/Plate + ID, validate, upload.
- New: `validate_metadata_against_omero` also returns `omero_plates`; per-plate status table built from the result: plate, in design, in OMERO, wells matched, wells missing.
- Tab shown only if `omero` is importable; otherwise a short note on how to install `mihcsme-py[omero]`. Rest of the app works offline.

## 6. Testing

- pytest: `tests/test_plate_ops.py` (edit, new field, missing wells, format detection, payload shape), form helper test.
- `marimo check` on all notebooks in `examples/marimo/`.
- One headless browser smoke test (playwright, marked `slow`, skipped if Chromium is missing): start `mihcsme_app.py`, click "Load example", assert the plate editor renders 96 or 384 wells and no page errors.
- OMERO code: existing tests only, no live server in CI.

## Error handling

- Excel parse errors: shown in the Load tab as a danger callout with the parser message (as today).
- Widget dependencies: the app's script header, `requirements.txt` and Docker image always install `mihcsme-py[app]`; importing `mihcsme_py.widgets` without them raises an ImportError with the install command.
- OMERO connection/validation failures: danger callout with the message; upload keeps the existing strict validation that refuses mismatched plates/wells.
