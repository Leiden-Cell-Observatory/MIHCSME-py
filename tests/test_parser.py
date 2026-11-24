"""Tests for Excel parser."""

import datetime
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


def test_date_typed_cells_raise_clear_error():
    """Excel silently turns text like the clone 'Oct4' into a real date.

    The parser must detect date-typed cells in AssayConditions and refuse to
    parse, naming the exact cells so the user can fix them in Excel.
    """
    df = pd.DataFrame(
        {
            "col0": ["Plate", "P1", "P1"],
            "col1": ["Well", "A01", "A02"],
            # Excel would store the antibody clone "Oct4" as a real date cell.
            "col2": [
                "Channel3AntibodyClone",
                datetime.datetime(2026, 10, 4),
                datetime.datetime(2026, 10, 4),
            ],
        }
    )

    excel_bytes = _make_excel_bytes(df)

    with pytest.raises(ValueError, match="Date-typed cells.*C3.*C4"):
        parse_excel_to_model(excel_bytes)


TEMPLATE_PATH = (
    __import__("pathlib").Path(__file__).parent.parent
    / "src"
    / "mihcsme_py"
    / "templates"
    / "LEI-MIHCSME.xlsx"
)


def test_reference_sheet_keeps_first_term_of_template():
    """Template reference sheets have no header row; the first term must not be dropped."""
    metadata = parse_excel_to_model(TEMPLATE_PATH)
    refs = {r.name: r.data for r in metadata.reference_sheets}

    assay_types = refs["_efo_assaytypes"]
    assert assay_types["high content analysis of cells"] == "http://www.ebi.ac.uk/efo/EFO_0005397"
    assert len(assay_types) == 8

    study_types = refs["_efo_studytypes"]
    assert study_types["high content analysis of cells"] == "http://www.ebi.ac.uk/efo/EFO_0005397"
    assert len(study_types) == 3

    assert (
        refs["_fbbiVisualizationMethods"]["visualization method"]
        == "http://purl.obolibrary.org/obo/FBbi_00000031"
    )


def test_reference_sheet_round_trip_keeps_all_entries(tmp_path):
    """Sheets written by write_metadata_to_excel have a Key/Value header; all entries survive."""
    from mihcsme_py.models import MIHCSMEMetadata, ReferenceSheet
    from mihcsme_py.writer import write_metadata_to_excel

    data = {"Human": "Homo sapiens", "Mouse": "Mus musculus", "Other": None}
    metadata = MIHCSMEMetadata(reference_sheets=[ReferenceSheet(name="_Organisms", data=data)])
    out = tmp_path / "refs.xlsx"
    write_metadata_to_excel(metadata, out)

    parsed = parse_excel_to_model(out)
    refs = {r.name: r.data for r in parsed.reference_sheets}
    assert refs["_Organisms"] == data
