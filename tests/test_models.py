"""Tests for Pydantic models."""

import pytest

from mihcsme_py.models import (
    AssayCondition,
    AssayInformation,
    DataOwner,
    InvestigationInfo,
    InvestigationInformation,
    MIHCSMEMetadata,
    StudyInformation,
)


def test_investigation_information_creation():
    """Test creating InvestigationInformation model."""
    inv_info = InvestigationInformation(
        data_owner=DataOwner(first_name="Jane", last_name="Doe"),
        investigation_info=InvestigationInfo(
            project_id="INV-001",
            investigation_title="Test Investigation",
        ),
    )
    assert "DataOwner" in inv_info.groups
    assert inv_info.groups["DataOwner"]["First Name"] == "Jane"
    assert "InvestigationInfo" in inv_info.groups
    assert inv_info.groups["InvestigationInfo"]["Project ID"] == "INV-001"


def test_assay_condition_well_normalization():
    """Test that well names are normalized to zero-padded format."""
    # Test non-padded input
    condition = AssayCondition(
        plate="Plate1",
        well="A1",
        conditions={"Compound": "DMSO"},
    )
    assert condition.well == "A01"

    # Test already padded input
    condition2 = AssayCondition(
        plate="Plate1",
        well="A01",
        conditions={"Compound": "DMSO"},
    )
    assert condition2.well == "A01"

    # Test uppercase conversion
    condition3 = AssayCondition(
        plate="Plate1",
        well="a1",
        conditions={"Compound": "DMSO"},
    )
    assert condition3.well == "A01"


def test_assay_condition_well_validation():
    """Test that invalid well names raise errors."""
    # Invalid row letter (Z is beyond P)
    with pytest.raises(ValueError, match="Invalid row letter"):
        AssayCondition(
            plate="Plate1",
            well="Z1",
            conditions={},
        )

    # Invalid column number (50 > 48)
    with pytest.raises(ValueError, match="Invalid well format"):
        AssayCondition(
            plate="Plate1",
            well="A50",
            conditions={},
        )

    # Invalid format
    with pytest.raises(ValueError, match="Invalid well format"):
        AssayCondition(
            plate="Plate1",
            well="Invalid",
            conditions={},
        )


def test_mihcsme_metadata_to_omero_dict():
    """Test conversion from Pydantic model to OMERO dict format."""
    metadata = MIHCSMEMetadata(
        investigation_information=InvestigationInformation(
            investigation_info=InvestigationInfo(project_id="INV-001")
        ),
        assay_conditions=[
            AssayCondition(
                plate="Plate1",
                well="A01",
                conditions={"Compound": "DMSO"},
            )
        ],
    )

    omero_dict = metadata.to_omero_dict()

    assert "InvestigationInformation" in omero_dict
    assert (
        omero_dict["InvestigationInformation"]["InvestigationInfo"]["Project ID"]
        == "INV-001"
    )
    assert "AssayConditions" in omero_dict
    assert len(omero_dict["AssayConditions"]) == 1
    assert omero_dict["AssayConditions"][0]["Plate"] == "Plate1"
    assert omero_dict["AssayConditions"][0]["Well"] == "A01"
    assert omero_dict["AssayConditions"][0]["Compound"] == "DMSO"


def test_mihcsme_metadata_from_omero_dict():
    """Test conversion from OMERO dict format to Pydantic model."""
    omero_dict = {
        "InvestigationInformation": {
            "DataOwner": {"First Name": "Jane", "Last Name": "Doe"},
            "InvestigationInformation": {"Project ID": "INV-001"},
        },
        "StudyInformation": {"Study": {"Study Title": "Test Study"}},
        "AssayInformation": {"Assay": {"Assay Type": "Microscopy"}},
        "AssayConditions": [
            {"Plate": "Plate1", "Well": "A01", "Compound": "DMSO"},
            {"Plate": "Plate1", "Well": "A02", "Compound": "Drug1"},
        ],
        "_Organisms": {"Human": "Homo sapiens"},
    }

    metadata = MIHCSMEMetadata.from_omero_dict(omero_dict)

    assert metadata.investigation_information is not None
    assert "DataOwner" in metadata.investigation_information.groups
    assert metadata.investigation_information.groups["DataOwner"]["First Name"] == "Jane"
    assert metadata.study_information is not None
    assert metadata.assay_information is not None
    assert len(metadata.assay_conditions) == 2
    assert metadata.assay_conditions[0].plate == "Plate1"
    assert metadata.assay_conditions[0].well == "A01"
    assert metadata.assay_conditions[0].conditions["Compound"] == "DMSO"
    assert len(metadata.reference_sheets) == 1
    assert metadata.reference_sheets[0].name == "_Organisms"


def test_round_trip_conversion():
    """Test that converting to dict and back preserves data."""
    original = MIHCSMEMetadata(
        investigation_information=InvestigationInformation(
            data_owner=DataOwner(first_name="Jane", last_name="Doe"),
            investigation_info=InvestigationInfo(project_id="INV-001"),
        ),
        assay_conditions=[
            AssayCondition(plate="P1", well="A1", conditions={"Drug": "Aspirin"}),
            AssayCondition(plate="P1", well="B2", conditions={"Drug": "Control"}),
        ],
    )

    # Convert to dict
    omero_dict = original.to_omero_dict()

    # Convert back to model
    restored = MIHCSMEMetadata.from_omero_dict(omero_dict)

    # Verify all data is preserved
    assert restored.investigation_information is not None
    assert restored.investigation_information.data_owner is not None
    assert restored.investigation_information.data_owner.first_name == "Jane"
    assert len(restored.assay_conditions) == len(original.assay_conditions)
    assert restored.assay_conditions[0].well == "A01"  # Note: normalized from "A1"


def test_to_dataframe():
    """Test converting assay conditions to DataFrame."""
    import pandas as pd

    metadata = MIHCSMEMetadata(
        assay_conditions=[
            AssayCondition(
                plate="Plate1",
                well="A01",
                conditions={"Treatment": "DMSO", "Dose": "0.1", "DoseUnit": "µM"},
            ),
            AssayCondition(
                plate="Plate1",
                well="A02",
                conditions={"Treatment": "Drug", "Dose": "10", "DoseUnit": "µM"},
            ),
        ]
    )

    df = metadata.to_dataframe()

    # Check DataFrame structure
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "Plate" in df.columns
    assert "Well" in df.columns
    assert "Treatment" in df.columns
    assert "Dose" in df.columns
    assert "DoseUnit" in df.columns

    # Check values
    assert df.loc[0, "Plate"] == "Plate1"
    assert df.loc[0, "Well"] == "A01"
    assert df.loc[0, "Treatment"] == "DMSO"
    assert df.loc[1, "Dose"] == "10"


def test_to_dataframe_empty():
    """Test converting empty assay conditions to DataFrame."""
    import pandas as pd

    metadata = MIHCSMEMetadata(assay_conditions=[])
    df = metadata.to_dataframe()

    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_from_dataframe():
    """Test creating metadata from DataFrame."""
    import pandas as pd

    df = pd.DataFrame(
        {
            "Plate": ["Plate1", "Plate1"],
            "Well": ["A01", "A02"],
            "Treatment": ["DMSO", "Drug"],
            "Dose": ["0.1", "10"],
            "DoseUnit": ["µM", "µM"],
        }
    )

    metadata = MIHCSMEMetadata.from_dataframe(df)

    # Check structure
    assert len(metadata.assay_conditions) == 2
    assert metadata.assay_conditions[0].plate == "Plate1"
    assert metadata.assay_conditions[0].well == "A01"
    assert metadata.assay_conditions[0].conditions["Treatment"] == "DMSO"
    assert metadata.assay_conditions[1].conditions["Dose"] == "10"


def test_from_dataframe_with_nan():
    """Test creating metadata from DataFrame with NaN values."""
    import pandas as pd

    df = pd.DataFrame(
        {
            "Plate": ["Plate1", "Plate1"],
            "Well": ["A01", "A02"],
            "Treatment": ["DMSO", None],
            "Dose": [None, "10"],
        }
    )

    metadata = MIHCSMEMetadata.from_dataframe(df)

    # Check that NaN values are skipped
    assert len(metadata.assay_conditions) == 2
    assert "Treatment" in metadata.assay_conditions[0].conditions
    assert "Treatment" not in metadata.assay_conditions[1].conditions
    assert "Dose" not in metadata.assay_conditions[0].conditions
    assert "Dose" in metadata.assay_conditions[1].conditions


def test_from_dataframe_missing_required():
    """Test that from_dataframe raises error for missing required columns."""
    import pandas as pd

    # Missing Plate column
    df = pd.DataFrame({"Well": ["A01", "A02"], "Treatment": ["DMSO", "Drug"]})

    with pytest.raises(ValueError, match="DataFrame must have a 'Plate' column"):
        MIHCSMEMetadata.from_dataframe(df)

    # Missing Well column
    df = pd.DataFrame({"Plate": ["Plate1", "Plate1"], "Treatment": ["DMSO", "Drug"]})

    with pytest.raises(ValueError, match="DataFrame must have a 'Well' column"):
        MIHCSMEMetadata.from_dataframe(df)


def test_dataframe_round_trip():
    """Test that converting to DataFrame and back preserves data."""
    import pandas as pd

    original = MIHCSMEMetadata(
        assay_conditions=[
            AssayCondition(
                plate="Plate1",
                well="A01",
                conditions={"Treatment": "DMSO", "Dose": "0.1", "DoseUnit": "µM"},
            ),
            AssayCondition(
                plate="Plate2",
                well="B12",
                conditions={"Treatment": "Drug", "Dose": "10", "DoseUnit": "nM"},
            ),
        ]
    )

    # Convert to DataFrame
    df = original.to_dataframe()

    # Convert back to metadata
    restored = MIHCSMEMetadata.from_dataframe(df)

    # Verify data is preserved
    assert len(restored.assay_conditions) == len(original.assay_conditions)
    assert restored.assay_conditions[0].plate == original.assay_conditions[0].plate
    assert restored.assay_conditions[0].well == original.assay_conditions[0].well
    assert restored.assay_conditions[0].conditions == original.assay_conditions[0].conditions
    assert restored.assay_conditions[1].conditions == original.assay_conditions[1].conditions


def test_update_conditions_from_dataframe():
    """Test updating conditions while preserving other metadata."""
    import pandas as pd

    # Create metadata with conditions only (simple case)
    original = MIHCSMEMetadata(
        assay_conditions=[
            AssayCondition(
                plate="Plate1",
                well="A01",
                conditions={"Gene": "BRCA1", "Treatment": "Control"},
            ),
            AssayCondition(
                plate="Plate1",
                well="A02",
                conditions={"Gene": "TP53", "Treatment": "Drug"},
            ),
        ],
    )

    # Modify via DataFrame - add new columns
    df = original.to_dataframe()
    df["Gene_lower"] = df["Gene"].str.lower()
    df["Concentration"] = ["0", "10"]

    # Update conditions
    updated = original.update_conditions_from_dataframe(df)

    # Verify conditions updated with new columns
    assert len(updated.assay_conditions) == 2
    assert "Gene_lower" in updated.assay_conditions[0].conditions
    assert updated.assay_conditions[0].conditions["Gene_lower"] == "brca1"
    assert updated.assay_conditions[1].conditions["Gene_lower"] == "tp53"
    assert "Concentration" in updated.assay_conditions[0].conditions
    assert updated.assay_conditions[0].conditions["Concentration"] == "0"
    assert updated.assay_conditions[1].conditions["Concentration"] == "10"

    # Verify original columns still present
    assert updated.assay_conditions[0].conditions["Gene"] == "BRCA1"
    assert updated.assay_conditions[1].conditions["Treatment"] == "Drug"
