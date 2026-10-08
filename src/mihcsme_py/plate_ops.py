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
