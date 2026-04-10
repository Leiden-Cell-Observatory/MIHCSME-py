"""Tests for OMERO upload validation."""

from unittest.mock import MagicMock, patch

import pytest

from mihcsme_py.models import AssayCondition, MIHCSMEMetadata
from mihcsme_py.uploader import upload_metadata_to_omero, validate_metadata_against_omero


def _make_mock_plate(name, plate_id, wells):
    """Create a mock OMERO plate with wells.

    Args:
        name: Plate name
        plate_id: Plate ID
        wells: List of (row, col) tuples (0-indexed)
    """
    plate = MagicMock()
    plate.getName.return_value = name
    plate.getId.return_value = plate_id

    mock_wells = []
    for row, col in wells:
        well = MagicMock()
        well.row = row
        well.column = col
        well.getId.return_value = row * 100 + col
        mock_wells.append(well)

    plate.listChildren.return_value = mock_wells
    return plate


def _make_metadata(*plate_wells):
    """Create MIHCSMEMetadata with assay conditions.

    Args:
        plate_wells: Tuples of (plate_name, [well_names])
            e.g. ("Plate1", ["A01", "A02"]), ("Plate2", ["B01"])
    """
    conditions = []
    for plate_name, wells in plate_wells:
        for well in wells:
            conditions.append(
                AssayCondition(plate=plate_name, well=well, conditions={"Treatment": "DMSO"})
            )
    return MIHCSMEMetadata(assay_conditions=conditions)


class TestValidateMetadataAgainstOmero:
    def test_validation_passes_when_all_match(self):
        conn = MagicMock()
        plate = _make_mock_plate("Plate1", 1, [(0, 0), (0, 1)])  # A01, A02
        metadata = _make_metadata(("Plate1", ["A01", "A02"]))

        with patch("mihcsme_py.uploader._get_plates_to_process", return_value=[plate]):
            with patch("mihcsme_py.uploader.get_wells_from_plate") as mock_wells:
                mock_wells.return_value = plate.listChildren()
                result = validate_metadata_against_omero(conn, metadata, "Screen", 1)

        assert result["valid"] is True
        assert result["errors"] == []

    def test_validation_error_plates_in_metadata_not_omero(self):
        conn = MagicMock()
        plate = _make_mock_plate("Plate1", 1, [(0, 0)])
        metadata = _make_metadata(("Plate1", ["A01"]), ("Plate2", ["A01"]))

        with patch("mihcsme_py.uploader._get_plates_to_process", return_value=[plate]):
            with patch("mihcsme_py.uploader.get_wells_from_plate") as mock_wells:
                mock_wells.return_value = plate.listChildren()
                result = validate_metadata_against_omero(conn, metadata, "Screen", 1)

        assert result["valid"] is False
        assert any("Plate2" in err for err in result["errors"])
        assert "Plate2" in result["plates"]["in_metadata_not_omero"]

    def test_validation_warning_plates_in_omero_not_metadata(self):
        conn = MagicMock()
        plate1 = _make_mock_plate("Plate1", 1, [(0, 0)])
        plate2 = _make_mock_plate("Plate2", 2, [(0, 0)])
        metadata = _make_metadata(("Plate1", ["A01"]))

        with patch("mihcsme_py.uploader._get_plates_to_process", return_value=[plate1, plate2]):
            with patch("mihcsme_py.uploader.get_wells_from_plate") as mock_wells:
                mock_wells.return_value = plate1.listChildren()
                result = validate_metadata_against_omero(conn, metadata, "Screen", 1)

        assert result["valid"] is True
        assert any("Plate2" in w for w in result["warnings"])
        assert "Plate2" in result["plates"]["in_omero_not_metadata"]

    def test_validation_error_wells_in_metadata_not_omero(self):
        conn = MagicMock()
        plate = _make_mock_plate("Plate1", 1, [(0, 0)])  # Only A01
        metadata = _make_metadata(("Plate1", ["A01", "A02", "B03"]))

        with patch("mihcsme_py.uploader._get_plates_to_process", return_value=[plate]):
            with patch("mihcsme_py.uploader.get_wells_from_plate") as mock_wells:
                mock_wells.return_value = plate.listChildren()
                result = validate_metadata_against_omero(conn, metadata, "Screen", 1)

        assert result["valid"] is False
        assert any("A02" in err for err in result["errors"])
        assert any("B03" in err for err in result["errors"])
        assert "A02" in result["wells"]["Plate1"]["in_metadata_not_omero"]
        assert "B03" in result["wells"]["Plate1"]["in_metadata_not_omero"]

    def test_validation_warning_wells_in_omero_not_metadata(self):
        conn = MagicMock()
        plate = _make_mock_plate("Plate1", 1, [(0, 0), (0, 1), (1, 0)])  # A01, A02, B01
        metadata = _make_metadata(("Plate1", ["A01"]))

        with patch("mihcsme_py.uploader._get_plates_to_process", return_value=[plate]):
            with patch("mihcsme_py.uploader.get_wells_from_plate") as mock_wells:
                mock_wells.return_value = plate.listChildren()
                result = validate_metadata_against_omero(conn, metadata, "Screen", 1)

        assert result["valid"] is True
        assert any("A02" in w for w in result["warnings"])
        assert any("B01" in w for w in result["warnings"])

    def test_validation_target_not_found(self):
        conn = MagicMock()
        metadata = _make_metadata(("Plate1", ["A01"]))

        with patch("mihcsme_py.uploader._get_plates_to_process", return_value=[]):
            result = validate_metadata_against_omero(conn, metadata, "Screen", 999)

        assert result["valid"] is False
        assert any("not found" in err for err in result["errors"])

    def test_validation_no_assay_conditions(self):
        conn = MagicMock()
        plate = _make_mock_plate("Plate1", 1, [(0, 0)])
        metadata = MIHCSMEMetadata(assay_conditions=[])

        with patch("mihcsme_py.uploader._get_plates_to_process", return_value=[plate]):
            result = validate_metadata_against_omero(conn, metadata, "Screen", 1)

        assert result["valid"] is True
        assert any("No assay conditions" in w for w in result["warnings"])


class TestUploadStrictMode:
    def test_upload_strict_blocks_on_validation_error(self):
        conn = MagicMock()
        plate = _make_mock_plate("Plate1", 1, [(0, 0)])
        metadata = _make_metadata(("Plate1", ["A01"]), ("Plate2", ["A01"]))

        with patch("mihcsme_py.uploader._get_plates_to_process", return_value=[plate]):
            with patch("mihcsme_py.uploader.get_wells_from_plate") as mock_wells:
                mock_wells.return_value = plate.listChildren()
                with patch("mihcsme_py.uploader.create_map_annotation") as mock_create:
                    result = upload_metadata_to_omero(
                        conn, metadata, "Screen", 1, strict=True
                    )
                    mock_create.assert_not_called()

        assert result["status"] == "error"
        assert "Plate2" in result["message"]
        assert result["validation"]["valid"] is False

    def test_upload_non_strict_proceeds_with_warnings(self):
        conn = MagicMock()
        plate = _make_mock_plate("Plate1", 1, [(0, 0)])
        metadata = _make_metadata(("Plate1", ["A01"]), ("Plate2", ["A01"]))

        with patch("mihcsme_py.uploader._get_plates_to_process", return_value=[plate]):
            with patch("mihcsme_py.uploader.get_wells_from_plate") as mock_wells:
                mock_wells.return_value = plate.listChildren()
                with patch(
                    "mihcsme_py.uploader.create_map_annotation", return_value=100
                ):
                    with patch("mihcsme_py.uploader._remove_metadata_recursive"):
                        result = upload_metadata_to_omero(
                            conn, metadata, "Screen", 1, strict=False
                        )

        assert result["status"] in ("success", "partial_success")
        assert result["validation"]["valid"] is False
        assert result["wells_succeeded"] >= 0
