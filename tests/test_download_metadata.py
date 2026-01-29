"""Tests for download_metadata_from_omero function."""

import pytest
from unittest.mock import Mock
from mihcsme_py.uploader import download_metadata_from_omero, _organize_into_groups
from mihcsme_py.models import MIHCSMEMetadata


class TestOrganizeIntoGroups:
    """Test the _organize_into_groups helper function."""

    def test_organize_investigation_fields(self):
        """Test that investigation fields are properly grouped."""
        flat_dict = {
            "First Name": "John",
            "Last Name": "Doe",
            "E-Mail Address": "john@example.com",
            "ORCID investigator": "https://orcid.org/0000-0002-3704-3675",
            "Project ID": "EuTOX",
            "Investigation Title": "Test Investigation",
        }

        result = _organize_into_groups(flat_dict)

        assert "DataOwner" in result
        assert result["DataOwner"]["First Name"] == "John"
        assert result["DataOwner"]["Last Name"] == "Doe"
        assert result["DataOwner"]["E-Mail Address"] == "john@example.com"
        assert result["DataOwner"]["ORCID investigator"] == "https://orcid.org/0000-0002-3704-3675"

        assert "InvestigationInfo" in result
        assert result["InvestigationInfo"]["Project ID"] == "EuTOX"
        assert result["InvestigationInfo"]["Investigation Title"] == "Test Investigation"

    def test_organize_study_fields(self):
        """Test that study fields are properly grouped."""
        flat_dict = {
            "Study Title": "Test Study",
            "Study internal ID": "STD-001",
            "Biosample Taxon": "NCBITAXON:9606",
            "Biosample Organism": "Human",
            "Library File Name": "library.csv",
            "Library Type": "siRNA",
            "HCS library protocol": "https://protocols.io/...",
            "Plate type": "uclear",
        }

        result = _organize_into_groups(flat_dict)

        assert "Study" in result
        assert result["Study"]["Study Title"] == "Test Study"
        assert result["Study"]["Study internal ID"] == "STD-001"

        assert "Biosample" in result
        assert result["Biosample"]["Biosample Taxon"] == "NCBITAXON:9606"
        assert result["Biosample"]["Biosample Organism"] == "Human"

        assert "Library" in result
        assert result["Library"]["Library File Name"] == "library.csv"

        assert "Protocols" in result
        assert result["Protocols"]["HCS library protocol"] == "https://protocols.io/..."

        assert "Plate" in result
        assert result["Plate"]["Plate type"] == "uclear"

    def test_organize_assay_fields(self):
        """Test that assay fields are properly grouped."""
        flat_dict = {
            "Assay Title": "Test Assay",
            "Assay internal ID": "ASY-001",
            "Number of plates": "10",
            "Imaging protocol": "https://protocols.io/imaging",
            "Sample preparation protocol": "Fixed cells",
            "Cell lines storage location": "Lab freezer",
            "Image number of pixelsX": "2048",
            "Image number of pixelsY": "2048",
            "Image number of channels": "4",
            "Image sites per well": "9",
            "Microscope id": "https://microscope.example.com",
            "Channel Transmission id": "1",
            "Channel 1 visualization method": "Fluorescence",
        }

        result = _organize_into_groups(flat_dict)

        assert "Assay" in result
        assert result["Assay"]["Assay Title"] == "Test Assay"
        assert result["Assay"]["Number of plates"] == "10"

        assert "AssayComponent" in result
        assert result["AssayComponent"]["Imaging protocol"] == "https://protocols.io/imaging"
        assert result["AssayComponent"]["Sample preparation protocol"] == "Fixed cells"

        assert "Biosample" in result
        assert result["Biosample"]["Cell lines storage location"] == "Lab freezer"

        assert "ImageData" in result
        assert result["ImageData"]["Image number of pixelsX"] == "2048"
        assert result["ImageData"]["Image number of pixelsY"] == "2048"
        assert result["ImageData"]["Image number of channels"] == "4"
        assert result["ImageData"]["Image sites per well"] == "9"

        assert "ImageAcquisition" in result
        assert result["ImageAcquisition"]["Microscope id"] == "https://microscope.example.com"

        assert "Specimen" in result
        assert result["Specimen"]["Channel Transmission id"] == "1"
        assert result["Specimen"]["Channel 1 visualization method"] == "Fluorescence"

    def test_organize_orcid_collaborators(self):
        """Test that ORCID collaborator fields are properly grouped."""
        flat_dict = {
            "ORCID  Data Collaborator_0": "https://orcid.org/0000-0001-1111-1111",
            "ORCID  Data Collaborator_1": "https://orcid.org/0000-0002-2222-2222",
        }

        result = _organize_into_groups(flat_dict)

        assert "DataCollaborator" in result
        assert "ORCID  Data Collaborator_0" in result["DataCollaborator"]
        assert "ORCID  Data Collaborator_1" in result["DataCollaborator"]

    def test_unknown_fields_go_to_metadata(self):
        """Test that unknown fields are grouped into 'Metadata' fallback."""
        flat_dict = {
            "Unknown Field 1": "value1",
            "Random Key": "value2",
        }

        result = _organize_into_groups(flat_dict)

        assert "Metadata" in result
        assert result["Metadata"]["Unknown Field 1"] == "value1"
        assert result["Metadata"]["Random Key"] == "value2"


class TestDownloadMetadataFromOmero:
    """Test the download_metadata_from_omero function."""

    def test_download_from_screen_with_complete_metadata(self):
        """Test downloading complete metadata from a Screen."""
        # Create mock connection and screen
        mock_conn = Mock()
        mock_screen = Mock()
        mock_screen.getName.return_value = "Test Screen"

        # Create mock plate
        mock_plate = Mock()
        mock_plate.getName.return_value = "Plate1"

        # Create mock wells
        mock_well1 = Mock()
        mock_well1.getRow.return_value = 0  # Row A
        mock_well1.getColumn.return_value = 0  # Column 1

        mock_well2 = Mock()
        mock_well2.getRow.return_value = 0  # Row A
        mock_well2.getColumn.return_value = 1  # Column 2

        # Create mock MapAnnotations for the screen with proper 3-level namespaces
        # InvestigationInformation/DataOwner
        inv_dataowner_ann = Mock()
        inv_dataowner_ann.getNs.return_value = "MIHCSME/InvestigationInformation/DataOwner"
        inv_dataowner_ann.getValue.return_value = [
            ("First Name", "Jane"),
            ("Last Name", "Doe"),
            ("E-Mail Address", "jane@example.com"),
        ]

        # InvestigationInformation/InvestigationInfo
        inv_info_ann = Mock()
        inv_info_ann.getNs.return_value = "MIHCSME/InvestigationInformation/InvestigationInfo"
        inv_info_ann.getValue.return_value = [
            ("Project ID", "EuTOX"),
            ("Investigation Title", "Test Investigation"),
        ]

        # StudyInformation/Study
        study_ann = Mock()
        study_ann.getNs.return_value = "MIHCSME/StudyInformation/Study"
        study_ann.getValue.return_value = [
            ("Study Title", "Test Study"),
            ("Study internal ID", "STD-001"),
        ]

        # StudyInformation/Biosample
        study_biosample_ann = Mock()
        study_biosample_ann.getNs.return_value = "MIHCSME/StudyInformation/Biosample"
        study_biosample_ann.getValue.return_value = [
            ("Biosample Organism", "Human"),
        ]

        # AssayInformation/Assay
        assay_ann = Mock()
        assay_ann.getNs.return_value = "MIHCSME/AssayInformation/Assay"
        assay_ann.getValue.return_value = [
            ("Assay Title", "Test Assay"),
            ("Assay internal ID", "ASY-001"),
        ]

        # AssayInformation/ImageData
        assay_imagedata_ann = Mock()
        assay_imagedata_ann.getNs.return_value = "MIHCSME/AssayInformation/ImageData"
        assay_imagedata_ann.getValue.return_value = [
            ("Image number of pixelsX", "2048"),
            ("Image number of pixelsY", "2048"),
            ("Image number of channels", "4"),
        ]

        mock_screen.listAnnotations.return_value = [
            inv_dataowner_ann,
            inv_info_ann,
            study_ann,
            study_biosample_ann,
            assay_ann,
            assay_imagedata_ann,
        ]

        # Create mock well annotations
        well1_ann = Mock()
        well1_ann.getNs.return_value = "MIHCSME/AssayConditions"
        well1_ann.getValue.return_value = [
            ("Treatment", "DMSO"),
            ("Dose", "0.1"),
        ]

        well2_ann = Mock()
        well2_ann.getNs.return_value = "MIHCSME/AssayConditions"
        well2_ann.getValue.return_value = [
            ("Treatment", "Drug"),
            ("Dose", "10"),
        ]

        mock_well1.listAnnotations.return_value = [well1_ann]
        mock_well2.listAnnotations.return_value = [well2_ann]

        # Setup mock hierarchy
        mock_plate.listChildren.return_value = [mock_well1, mock_well2]
        mock_screen.listChildren.return_value = [mock_plate]
        mock_conn.getObject.return_value = mock_screen

        # Call the function
        metadata = download_metadata_from_omero(
            conn=mock_conn,
            target_type="Screen",
            target_id=123,
            namespace="MIHCSME",
        )

        # Verify the metadata structure
        assert metadata is not None
        assert isinstance(metadata, MIHCSMEMetadata)

        # Check Investigation Information
        assert metadata.investigation_information is not None
        assert metadata.investigation_information.data_owner is not None
        assert metadata.investigation_information.data_owner.first_name == "Jane"
        assert metadata.investigation_information.data_owner.last_name == "Doe"
        assert metadata.investigation_information.investigation_info is not None
        assert metadata.investigation_information.investigation_info.project_id == "EuTOX"

        # Check Study Information
        assert metadata.study_information is not None
        assert metadata.study_information.study is not None
        assert metadata.study_information.study.study_title == "Test Study"
        assert metadata.study_information.biosample is not None
        assert metadata.study_information.biosample.biosample_organism == "Human"

        # Check Assay Information
        assert metadata.assay_information is not None
        assert metadata.assay_information.assay is not None
        assert metadata.assay_information.assay.assay_title == "Test Assay"
        assert metadata.assay_information.image_data is not None
        assert metadata.assay_information.image_data.image_number_of_pixelsx == "2048"
        assert metadata.assay_information.image_data.image_number_of_pixelsy == "2048"

        # Check Assay Conditions
        assert len(metadata.assay_conditions) == 2
        assert metadata.assay_conditions[0].plate == "Plate1"
        assert metadata.assay_conditions[0].well == "A01"
        assert metadata.assay_conditions[0].conditions["Treatment"] == "DMSO"
        assert metadata.assay_conditions[1].well == "A02"
        assert metadata.assay_conditions[1].conditions["Treatment"] == "Drug"

    def test_download_from_plate(self):
        """Test downloading metadata from a single Plate."""
        mock_conn = Mock()
        mock_plate = Mock()
        mock_plate.getName.return_value = "TestPlate"

        # Create mock well
        mock_well = Mock()
        mock_well.getRow.return_value = 1  # Row B
        mock_well.getColumn.return_value = 5  # Column 6

        # Create mock well annotation
        well_ann = Mock()
        well_ann.getNs.return_value = "MIHCSME/AssayConditions"
        well_ann.getValue.return_value = [("CellLine", "HeLa")]

        mock_well.listAnnotations.return_value = [well_ann]
        mock_plate.listChildren.return_value = [mock_well]
        mock_plate.listAnnotations.return_value = []
        mock_conn.getObject.return_value = mock_plate

        # Call the function
        metadata = download_metadata_from_omero(
            conn=mock_conn,
            target_type="Plate",
            target_id=456,
        )

        # Verify
        assert metadata is not None
        assert len(metadata.assay_conditions) == 1
        assert metadata.assay_conditions[0].plate == "TestPlate"
        assert metadata.assay_conditions[0].well == "B06"
        assert metadata.assay_conditions[0].conditions["CellLine"] == "HeLa"

    def test_download_raises_error_when_object_not_found(self):
        """Test that an error is raised when the object doesn't exist."""
        mock_conn = Mock()
        mock_conn.getObject.return_value = None

        with pytest.raises(ValueError, match="Screen with ID 999 not found"):
            download_metadata_from_omero(
                conn=mock_conn,
                target_type="Screen",
                target_id=999,
            )

    def test_download_handles_empty_wells(self):
        """Test that wells without metadata are skipped."""
        mock_conn = Mock()
        mock_plate = Mock()
        mock_plate.getName.return_value = "TestPlate"

        # Create mock well with no annotations
        mock_well = Mock()
        mock_well.getRow.return_value = 0
        mock_well.getColumn.return_value = 0
        mock_well.listAnnotations.return_value = []

        mock_plate.listChildren.return_value = [mock_well]
        mock_plate.listAnnotations.return_value = []
        mock_conn.getObject.return_value = mock_plate

        metadata = download_metadata_from_omero(
            conn=mock_conn,
            target_type="Plate",
            target_id=123,
        )

        # Should have no assay conditions
        assert len(metadata.assay_conditions) == 0
