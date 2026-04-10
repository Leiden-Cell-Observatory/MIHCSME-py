"""Tests for Excel parser."""

import io

import pandas as pd
import pytest

from mihcsme_py.parser import parse_excel_to_model


def _make_excel_bytes(assay_conditions_df, include_standard_sheets=True):
    """Create a minimal MIHCSME Excel file in memory."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        if include_standard_sheets:
            # Minimal key-value sheets with required structure
            for sheet in ["InvestigationInformation", "StudyInformation", "AssayInformation"]:
                kv_df = pd.DataFrame(
                    {"Annotation_groups": ["#comment"], "Key": ["#comment"], "Value": ["#comment"]}
                )
                kv_df.to_excel(writer, sheet_name=sheet, index=False)

        assay_conditions_df.to_excel(writer, sheet_name="AssayConditions", index=False)

    buf.seek(0)
    return buf.read()


def test_duplicate_column_names_raises_clear_error():
    """Duplicate column names in AssayConditions should list the duplicated columns."""
    # Build a DataFrame that has duplicate column headers
    # The first row is the actual header row in MIHCSME format
    df = pd.DataFrame(
        {
            "col0": ["Plate", "Plate1", "Plate1"],
            "col1": ["Well", "A01", "A02"],
            "col2": ["Treatment", "DMSO", "Drug"],
            "col3": ["Treatment", "high", "low"],  # Duplicate!
        }
    )

    excel_bytes = _make_excel_bytes(df)

    with pytest.raises(ValueError, match="Duplicate column names.*Treatment"):
        parse_excel_to_model(excel_bytes)
