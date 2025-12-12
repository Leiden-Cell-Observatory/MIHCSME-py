"""Tests for Pydantic models."""

import pytest

from mihcsme_omero.models import (
    AssayCondition,
    AssayInformation,
    InvestigationInformation,
    MIHCSMEMetadata,
    StudyInformation,
)


def test_investigation_information_creation():
    """Test creating InvestigationInformation model."""
    inv_info = InvestigationInformation(
        groups={
            "Investigation": {
                "Investigation Identifier": "INV-001",
                "Investigation Title": "Test Investigation",
            }
        }
    )
    assert "Investigation" in inv_info.groups
    assert inv_info.groups["Investigation"]["Investigation Identifier"] == "INV-001"


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
    # Invalid row letter
    with pytest.raises(ValueError, match="Invalid row letter"):
        AssayCondition(
            plate="Plate1",
            well="Z1",
            conditions={},
        )

    # Invalid column number
    with pytest.raises(ValueError, match="Invalid column number"):
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
            groups={"Investigation": {"ID": "INV-001"}}
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
    assert omero_dict["InvestigationInformation"]["Investigation"]["ID"] == "INV-001"
    assert "AssayConditions" in omero_dict
    assert len(omero_dict["AssayConditions"]) == 1
    assert omero_dict["AssayConditions"][0]["Plate"] == "Plate1"
    assert omero_dict["AssayConditions"][0]["Well"] == "A01"
    assert omero_dict["AssayConditions"][0]["Compound"] == "DMSO"


def test_mihcsme_metadata_from_omero_dict():
    """Test conversion from OMERO dict format to Pydantic model."""
    omero_dict = {
        "InvestigationInformation": {"Investigation": {"ID": "INV-001"}},
        "StudyInformation": {"Study": {"Title": "Test Study"}},
        "AssayInformation": {"Assay": {"Type": "Microscopy"}},
        "AssayConditions": [
            {"Plate": "Plate1", "Well": "A01", "Compound": "DMSO"},
            {"Plate": "Plate1", "Well": "A02", "Compound": "Drug1"},
        ],
        "_Organisms": {"Human": "Homo sapiens"},
    }

    metadata = MIHCSMEMetadata.from_omero_dict(omero_dict)

    assert metadata.investigation_information is not None
    assert metadata.investigation_information.groups["Investigation"]["ID"] == "INV-001"
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
            groups={"Investigation": {"ID": "INV-001", "Title": "Test"}}
        ),
        study_information=StudyInformation(groups={"Study": {"ID": "STD-001"}}),
        assay_information=AssayInformation(groups={"Assay": {"Type": "HCS"}}),
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
    assert (
        restored.investigation_information.groups["Investigation"]["ID"]
        == original.investigation_information.groups["Investigation"]["ID"]
    )
    assert len(restored.assay_conditions) == len(original.assay_conditions)
    assert restored.assay_conditions[0].well == "A01"  # Note: normalized from "A1"
