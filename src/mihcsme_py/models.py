"""Pydantic models for MIHCSME metadata structure."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    import pandas as pd


# ============================================================================
# Reusable Validators
# ============================================================================


def _coerce_to_string(v: Any) -> Optional[str]:
    """Convert any value to string, treating empty as None.

    Handles special cases like datetime objects (uses isoformat).

    Args:
        v: Any value to convert

    Returns:
        String representation or None if empty
    """
    if v is None or v == "":
        return None
    if hasattr(v, "isoformat"):  # Handle datetime/Timestamp
        return v.isoformat()
    return str(v)


def _validate_orcid(v: Optional[str]) -> Optional[str]:
    """Validate ORCID URL format.

    Args:
        v: ORCID URL string

    Returns:
        Validated ORCID URL or None

    Raises:
        ValueError: If ORCID doesn't start with https://orcid.org/
    """
    if v is None or v == "":
        return None
    if not v.startswith("https://orcid.org/"):
        raise ValueError("ORCID must be a URL starting with https://orcid.org/")
    return v


# ============================================================================
# Annotated Types for Common Patterns
# ============================================================================

# String that auto-coerces from numbers, dates, etc.
StringCoerced = Annotated[Optional[str], BeforeValidator(_coerce_to_string)]

# ORCID URL with validation
OrcidUrl = Annotated[Optional[str], BeforeValidator(_validate_orcid)]


# ============================================================================
# Helper Functions
# ============================================================================


def _model_to_dict_with_aliases(model: BaseModel) -> Dict[str, Any]:
    """Convert a Pydantic model to dictionary using field aliases.

    This helper automatically includes all non-None fields using their
    aliases (as defined in Field(alias=...)).

    Args:
        model: Pydantic model instance

    Returns:
        Dictionary with alias names as keys and field values
    """
    result = {}
    # Access model_fields from the class, not the instance
    for field_name, field_info in model.__class__.model_fields.items():
        value = getattr(model, field_name)
        if value is not None and value != "":
            # Use the alias if defined, otherwise use field name
            key = field_info.alias if field_info.alias else field_name
            result[key] = value
    return result


# ============================================================================
# Investigation Information Models
# ============================================================================


class DataOwner(BaseModel):
    """Data owner information."""

    first_name: Optional[str] = Field(None, alias="First Name", description="First Name")
    middle_names: Optional[str] = Field(
        None, alias="Middle Name(s)", description="Middle Name(s) if any"
    )
    last_name: Optional[str] = Field(None, alias="Last Name", description="Last Name")
    user_name: Optional[str] = Field(None, alias="User name", description="Institutional user name")
    institute: Optional[str] = Field(
        None,
        alias="Institute",
        description="Institute level, e.g. Universiteit Leiden, Faculty of Science, Institute of Biology",
    )
    email: Optional[str] = Field(
        None, alias="E-Mail Address", description="Institution email address"
    )
    orcid: OrcidUrl = Field(
        None,
        alias="ORCID investigator",
        description="ORCID ID as URL, e.g. https://orcid.org/0000-0002-3704-3675",
    )

    model_config = ConfigDict(populate_by_name=True)


class DataCollaborator(BaseModel):
    """Data collaborator information."""

    orcid: OrcidUrl = Field(
        None,
        alias="ORCID  Data Collaborator",
        description="ORCID ID of collaborator with experimental, collection or analysis part of this investigation",
    )

    model_config = ConfigDict(populate_by_name=True)


class InvestigationInfo(BaseModel):
    """Core investigation information."""

    project_id: StringCoerced = Field(
        None, alias="Project ID", description="EU/NWO/consortium ID – Examples: EuTOX"
    )
    investigation_title: Optional[str] = Field(
        None,
        alias="Investigation Title",
        description="High level concept to link related studies",
    )
    investigation_internal_id: StringCoerced = Field(
        None,
        alias="Investigation internal ID",
        description="Corresponding internal ID for your investigation",
    )
    investigation_description: Optional[str] = Field(
        None,
        alias="Investigation description",
        description="Short description for your investigation",
    )

    model_config = ConfigDict(populate_by_name=True)


class InvestigationInformation(BaseModel):
    """Investigation-level metadata with structured fields."""

    data_owner: Optional[DataOwner] = Field(None, description="Data owner information")
    data_collaborators: List[DataCollaborator] = Field(
        default_factory=list, description="List of data collaborators"
    )
    investigation_info: Optional[InvestigationInfo] = Field(
        None, description="Core investigation information"
    )

    @property
    def groups(self) -> Dict[str, Dict[str, Any]]:
        """Convert to groups dictionary format for OMERO upload."""
        return self.to_groups_dict()

    def to_groups_dict(self) -> Dict[str, Dict[str, Any]]:
        """Convert to groups dictionary format."""
        groups = {}

        # DataOwner group - automatically include all fields
        if self.data_owner:
            data = _model_to_dict_with_aliases(self.data_owner)
            if data:
                groups["DataOwner"] = data

        # DataCollaborator group
        if self.data_collaborators:
            groups["DataCollaborator"] = {}
            for i, collab in enumerate(self.data_collaborators):
                if collab.orcid:
                    # All use same key name per template
                    groups["DataCollaborator"][f"ORCID  Data Collaborator_{i}"] = collab.orcid

        # InvestigationInformation group - automatically include all fields
        if self.investigation_info:
            data = _model_to_dict_with_aliases(self.investigation_info)
            if data:
                groups["InvestigationInformation"] = data

        return groups

    @classmethod
    def from_groups_dict(cls, groups: Dict[str, Dict[str, Any]]) -> "InvestigationInformation":
        """Create from groups dictionary format."""
        # Parse DataOwner
        data_owner = None
        if "DataOwner" in groups:
            data_owner = DataOwner(**groups["DataOwner"])

        # Parse DataCollaborators
        data_collaborators = []
        if "DataCollaborator" in groups:
            for key, value in groups["DataCollaborator"].items():
                if "ORCID" in key and value:
                    data_collaborators.append(DataCollaborator(orcid=value))

        # Parse InvestigationInformation
        investigation_info = None
        if "InvestigationInformation" in groups:
            investigation_info = InvestigationInfo(**groups["InvestigationInformation"])

        return cls(
            data_owner=data_owner,
            data_collaborators=data_collaborators,
            investigation_info=investigation_info,
        )

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "data_owner": {
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "email": "j.doe@example.com",
                    "orcid": "https://orcid.org/0000-0002-3704-3675",
                },
                "investigation_info": {
                    "investigation_title": "Example Investigation",
                    "project_id": "EuTOX",
                },
            }
        },
    )


class Study(BaseModel):
    """Study information."""

    study_title: Optional[str] = Field(
        None,
        alias="Study Title",
        description="Manuscript/chapter/publication/paragraph title describing purpose or intention for one or multiple assays",
    )
    study_internal_id: StringCoerced = Field(
        None, alias="Study internal ID", description="Study ID, linked to ELN or lab journal"
    )
    study_description: Optional[str] = Field(
        None,
        alias="Study Description",
        description="Description of study with additional unstructured information",
    )
    study_key_words: Optional[str] = Field(
        None,
        alias="Study Key Words",
        description="List of key words associated with your study (EFO-terms)",
    )

    model_config = ConfigDict(populate_by_name=True)


class Biosample(BaseModel):
    """Biosample information."""

    biosample_taxon: Optional[str] = Field(
        None,
        alias="Biosample Taxon",
        description="NCBI-taxon id, human = NCBITAXON:9606",
    )
    biosample_description: Optional[str] = Field(
        None, alias="Biosample description", description="Description of biosample genotype"
    )
    biosample_organism: Optional[str] = Field(
        None,
        alias="Biosample Organism",
        description="Which organism is your cell lines or tissue from. Examples: Human or mouse",
    )
    number_of_cell_lines_used: StringCoerced = Field(
        None,
        alias="Number of cell lines used",
        description="In case multiple cell lines are used indicate here",
    )

    model_config = ConfigDict(populate_by_name=True)


class Library(BaseModel):
    """Library information."""

    library_file_name: Optional[str] = Field(
        None, alias="Library File Name", description="Library file info"
    )
    library_file_format: Optional[str] = Field(
        None, alias="Library File Format", description="Library file info"
    )
    library_type: Optional[str] = Field(None, alias="Library Type", description="Library file info")
    library_manufacturer: Optional[str] = Field(
        None, alias="Library Manufacturer", description="Library file info"
    )
    library_version: StringCoerced = Field(
        None, alias="Library Version", description="Library file info"
    )
    library_experimental_conditions: Optional[str] = Field(
        None,
        alias="Library Experimental Conditions",
        description="Any experimental conditions some cells were grown under as part of the study",
    )
    quality_control_description: Optional[str] = Field(
        None,
        alias="Quality Control Description",
        description="A brief description of the kind of quality control measures that were taken",
    )

    model_config = ConfigDict(populate_by_name=True)


class Protocols(BaseModel):
    """Protocol information."""

    hcs_library_protocol: Optional[str] = Field(
        None,
        alias="HCS library protocol",
        description="Url/doi protocols.io or ELN associated url. At least SOP/protocol filename",
    )
    growth_protocol: Optional[str] = Field(
        None,
        alias="growth protocol",
        description="Url/doi protocols.io or ELN associated url. At least SOP/protocol filename",
    )
    treatment_protocol: Optional[str] = Field(
        None,
        alias="treatment protocol",
        description="Url/doi protocols.io or ELN associated url. At least SOP/protocol filename",
    )
    hcs_data_analysis_protocol: Optional[str] = Field(
        None,
        alias="HCS data analysis protocol",
        description="Url/doi protocols.io or ELN associated url. At least SOP/protocol filename",
    )

    model_config = ConfigDict(populate_by_name=True)


class Plate(BaseModel):
    """Plate information."""

    plate_type: Optional[str] = Field(None, alias="Plate type", description="Example: uclear")
    plate_type_manufacturer: Optional[str] = Field(
        None, alias="Plate type Manufacturer", description="Example: Greiner Bio-One"
    )
    plate_type_catalog_number: StringCoerced = Field(
        None, alias="Plate type Catalog number", description="Example: 781081"
    )

    model_config = ConfigDict(populate_by_name=True)


class StudyInformation(BaseModel):
    """Study-level metadata with structured fields."""

    study: Optional[Study] = Field(None, description="Study information")
    biosample: Optional[Biosample] = Field(None, description="Biosample information")
    library: Optional[Library] = Field(None, description="Library information")
    protocols: Optional[Protocols] = Field(None, description="Protocol information")
    plate: Optional[Plate] = Field(None, description="Plate information")

    @property
    def groups(self) -> Dict[str, Dict[str, Any]]:
        """Convert to groups dictionary format for OMERO upload."""
        return self.to_groups_dict()

    def to_groups_dict(self) -> Dict[str, Dict[str, Any]]:
        """Convert to groups dictionary format."""
        groups = {}

        # Study group - automatically include all fields
        if self.study:
            data = _model_to_dict_with_aliases(self.study)
            if data:
                groups["Study"] = data

        # Biosample group - automatically include all fields
        if self.biosample:
            data = _model_to_dict_with_aliases(self.biosample)
            if data:
                groups["Biosample"] = data

        # Library group - automatically include all fields
        if self.library:
            data = _model_to_dict_with_aliases(self.library)
            if data:
                groups["Library"] = data

        # Protocols group - automatically include all fields
        if self.protocols:
            data = _model_to_dict_with_aliases(self.protocols)
            if data:
                groups["Protocols"] = data

        # Plate group - automatically include all fields
        if self.plate:
            data = _model_to_dict_with_aliases(self.plate)
            if data:
                groups["Plate"] = data

        return groups

    @classmethod
    def from_groups_dict(cls, groups: Dict[str, Dict[str, Any]]) -> "StudyInformation":
        """Create from groups dictionary format."""
        # Parse Study
        study = None
        if "Study" in groups:
            study = Study(**groups["Study"])

        # Parse Biosample
        biosample = None
        if "Biosample" in groups:
            biosample = Biosample(**groups["Biosample"])

        # Parse Library
        library = None
        if "Library" in groups:
            library = Library(**groups["Library"])

        # Parse Protocols
        protocols = None
        if "Protocols" in groups:
            protocols = Protocols(**groups["Protocols"])

        # Parse Plate
        plate = None
        if "Plate" in groups:
            plate = Plate(**groups["Plate"])

        return cls(
            study=study, biosample=biosample, library=library, protocols=protocols, plate=plate
        )

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "study": {
                    "study_title": "Example Study",
                    "study_internal_id": "STD-001",
                },
                "biosample": {"biosample_organism": "Human"},
            }
        },
    )


class Assay(BaseModel):
    """Assay information."""

    assay_title: Optional[str] = Field(None, alias="Assay Title", description="Screen name")
    assay_internal_id: StringCoerced = Field(
        None,
        alias="Assay internal ID",
        description="Experimental ID, e.g. aMV-010, linked to ELN or labjournal",
    )
    assay_description: Optional[str] = Field(
        None,
        alias="Assay Description",
        description="Description of screen plus additional unstructured information",
    )
    assay_number_of_biological_replicates: StringCoerced = Field(
        None,
        alias="Assay number of biological replicates",
        description="Total number of biol. Repl.",
    )
    number_of_plates: StringCoerced = Field(
        None, alias="Number of plates", description="Total number of plates, n-plates"
    )
    assay_technology_type: Optional[str] = Field(
        None, alias="Assay Technology Type", description="Imaging method, Fbbi terms"
    )
    assay_type: Optional[str] = Field(
        None,
        alias="Assay Type",
        description="List of options: sub types of HCS e.g. Gene Knock down, RNAi, compound, EFO terms",
    )
    assay_external_url: Optional[str] = Field(
        None,
        alias="Assay External URL",
        description="ELN or any other external url link to this screen",
    )
    assay_data_url: Optional[str] = Field(
        None, alias="Assay data URL", description="OMERO url link to this screen"
    )

    model_config = ConfigDict(populate_by_name=True)


class AssayComponent(BaseModel):
    """Assay component information."""

    imaging_protocol: Optional[str] = Field(
        None,
        alias="Imaging protocol",
        description="Url to protocols.io or protocols in ELN, at least protocol file name",
    )
    sample_preparation_protocol: Optional[str] = Field(
        None,
        alias="Sample preparation protocol",
        description="Sample preparation method (Formaldahyde (PFA) fixed tissue, Live cells, unfixed tissue)",
    )

    model_config = ConfigDict(populate_by_name=True)


class BiosampleAssay(BaseModel):
    """Biosample information specific to assay."""

    cell_lines_storage_location: Optional[str] = Field(
        None,
        alias="Cell lines storage location",
        description="Storage location according to Database used or at least location",
    )
    cell_lines_clone_number: StringCoerced = Field(
        None, alias="Cell lines clone number", description="Storage location DB info"
    )
    cell_lines_passage_number: StringCoerced = Field(
        None,
        alias="Cell lines Passage number",
        description="Passage number of your cells",
    )

    model_config = ConfigDict(populate_by_name=True)


class ImageData(BaseModel):
    """Image data information."""

    image_number_of_pixelsx: StringCoerced = Field(
        None,
        alias="Image number of pixelsX",
        description="Indicate number of pixels in x in images",
    )
    image_number_of_pixelsy: StringCoerced = Field(
        None,
        alias="Image number of pixelsY",
        description="Indicate number of pixels in y in images",
    )
    image_number_of_z_stacks: StringCoerced = Field(
        None,
        alias="Image number of  z-stacks",
        description="Indicate number z stacks in image, single image is z=1",
    )
    image_number_of_channels: StringCoerced = Field(
        None,
        alias="Image number of channels",
        description="Indicate number of channels in your image",
    )
    image_number_of_timepoints: StringCoerced = Field(
        None,
        alias="Image number of timepoints",
        description="Indicate number of time point(s) in your image",
    )
    image_sites_per_well: StringCoerced = Field(
        None, alias="Image sites per well", description="Number of fields, numeric value"
    )

    model_config = ConfigDict(populate_by_name=True)


class ImageAcquisition(BaseModel):
    """Image acquisition information."""

    microscope_id: StringCoerced = Field(
        None,
        alias="Microscope id",
        description="Url to micrometa app file link or other url describing your microscope",
    )

    model_config = ConfigDict(populate_by_name=True)


class Channel(BaseModel):
    """Single channel information for specimen imaging."""

    visualization_method: Optional[str] = Field(
        None, description="Visualization method (e.g., Hoechst staining, GFP)"
    )
    entity: Optional[str] = Field(None, description="Entity visualized (e.g., DNA, MAP1LC3B)")
    label: Optional[str] = Field(None, description="Label used for entity (e.g., Nuclei, GFP-LC3)")
    id: StringCoerced = Field(None, description="Sequential id of channel order in your image")

    model_config = ConfigDict(populate_by_name=True)


class Specimen(BaseModel):
    """Specimen/channel information with dynamic channel support.

    Channels are stored as a list internally but can be converted to/from
    the flat Excel format (Channel 1 visualization method, etc.).
    """

    channel_transmission_id: StringCoerced = Field(
        None,
        alias="Channel Transmission id",
        description="Channel id is dependent on different machines, first or last. If No transmission is acquired state NA",
    )
    channels: List[Channel] = Field(
        default_factory=list,
        description="List of channel information (supports up to 8 channels)",
    )

    model_config = ConfigDict(populate_by_name=True)

    def to_flat_dict(self) -> Dict[str, Any]:
        """Convert to flat dictionary format for Excel/OMERO export.

        Returns:
            Dictionary with keys like 'Channel Transmission id',
            'Channel 1 visualization method', 'Channel 1 entity', etc.
        """
        result: Dict[str, Any] = {}

        if self.channel_transmission_id:
            result["Channel Transmission id"] = self.channel_transmission_id

        for i, channel in enumerate(self.channels, start=1):
            if channel.visualization_method:
                result[f"Channel {i} visualization method"] = channel.visualization_method
            if channel.entity:
                result[f"Channel {i} entity"] = channel.entity
            if channel.label:
                result[f"Channel {i} label"] = channel.label
            if channel.id:
                result[f"Channel {i} id"] = channel.id

        return result

    @classmethod
    def from_flat_dict(cls, data: Dict[str, Any]) -> "Specimen":
        """Create Specimen from flat dictionary format (Excel/OMERO).

        Args:
            data: Dictionary with keys like 'Channel 1 visualization method', etc.

        Returns:
            Specimen instance with channels list populated
        """
        channel_transmission_id = data.get("Channel Transmission id")

        # Parse channels (support up to 8)
        channels = []
        for i in range(1, 9):
            vis_method = data.get(f"Channel {i} visualization method")
            entity = data.get(f"Channel {i} entity")
            label = data.get(f"Channel {i} label")
            ch_id = data.get(f"Channel {i} id")

            # Only add channel if it has any data
            if any([vis_method, entity, label, ch_id]):
                channels.append(
                    Channel(
                        visualization_method=vis_method,
                        entity=entity,
                        label=label,
                        id=ch_id,
                    )
                )

        return cls(channel_transmission_id=channel_transmission_id, channels=channels)


class AssayInformation(BaseModel):
    """Assay-level metadata with structured fields."""

    assay: Optional[Assay] = Field(None, description="Assay information")
    assay_component: Optional[AssayComponent] = Field(
        None, description="Assay component information"
    )
    biosample: Optional[BiosampleAssay] = Field(None, description="Biosample information")
    image_data: Optional[ImageData] = Field(None, description="Image data information")
    image_acquisition: Optional[ImageAcquisition] = Field(
        None, description="Image acquisition information"
    )
    specimen: Optional[Specimen] = Field(None, description="Specimen/channel information")

    @property
    def groups(self) -> Dict[str, Dict[str, Any]]:
        """Convert to groups dictionary format for OMERO upload."""
        return self.to_groups_dict()

    def to_groups_dict(self) -> Dict[str, Dict[str, Any]]:
        """Convert to groups dictionary format."""
        groups = {}

        # Assay group - automatically include all fields
        if self.assay:
            data = _model_to_dict_with_aliases(self.assay)
            if data:
                groups["Assay"] = data

        # AssayComponent group - automatically include all fields
        if self.assay_component:
            data = _model_to_dict_with_aliases(self.assay_component)
            if data:
                groups["AssayComponent"] = data

        # Biosample group - automatically include all fields
        if self.biosample:
            data = _model_to_dict_with_aliases(self.biosample)
            if data:
                groups["Biosample"] = data

        # ImageData group - automatically include all fields
        if self.image_data:
            data = _model_to_dict_with_aliases(self.image_data)
            if data:
                groups["ImageData"] = data

        # ImageAcquisition group - automatically include all fields
        if self.image_acquisition:
            data = _model_to_dict_with_aliases(self.image_acquisition)
            if data:
                groups["ImageAcquisition"] = data

        # Specimen group - use to_flat_dict() for Excel/OMERO compatibility
        if self.specimen:
            data = self.specimen.to_flat_dict()
            if data:
                groups["Specimen"] = data

        return groups

    @classmethod
    def from_groups_dict(cls, groups: Dict[str, Dict[str, Any]]) -> "AssayInformation":
        """Create from groups dictionary format."""
        # Parse Assay
        assay = None
        if "Assay" in groups:
            assay = Assay(**groups["Assay"])

        # Parse AssayComponent
        assay_component = None
        if "AssayComponent" in groups:
            assay_component = AssayComponent(**groups["AssayComponent"])

        # Parse Biosample
        biosample = None
        if "Biosample" in groups:
            biosample = BiosampleAssay(**groups["Biosample"])

        # Parse ImageData
        image_data = None
        if "ImageData" in groups:
            image_data = ImageData(**groups["ImageData"])

        # Parse ImageAcquisition
        image_acquisition = None
        if "ImageAcquisition" in groups:
            image_acquisition = ImageAcquisition(**groups["ImageAcquisition"])

        # Parse Specimen - use from_flat_dict() for Excel/OMERO compatibility
        specimen = None
        if "Specimen" in groups:
            specimen = Specimen.from_flat_dict(groups["Specimen"])

        return cls(
            assay=assay,
            assay_component=assay_component,
            biosample=biosample,
            image_data=image_data,
            image_acquisition=image_acquisition,
            specimen=specimen,
        )

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "assay": {
                    "assay_title": "Example Screen",
                    "assay_internal_id": "ASY-001",
                },
                "image_data": {"image_number_of_channels": "3"},
            }
        },
    )


class AssayCondition(BaseModel):
    """Single well condition from AssayConditions sheet.

    All metadata fields (Treatment, Dose, CellLine, etc.) are stored in the
    conditions dictionary for maximum flexibility.

    Attributes:
        plate: Plate identifier/name
        well: Well identifier (e.g., A01, B12) - auto-normalized
        conditions: Dictionary of all metadata key-value pairs for this well
    """

    plate: str = Field(..., description="Plate identifier/name")
    well: str = Field(..., description="Well identifier (e.g., A01, B12)")
    conditions: Dict[str, Any] = Field(
        default_factory=dict,
        description="All metadata fields for this well (Treatment, Dose, etc.)",
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "plate": "Plate1",
                "well": "A01",
                "conditions": {
                    "Treatment": "DMSO",
                    "Dose": "0.1",
                    "DoseUnit": "µM",
                    "CellLine": "HeLa",
                },
            }
        },
    )

    @field_validator("well")
    @classmethod
    def normalize_well_name(cls, v: str) -> str:
        """Normalize well names to zero-padded format (A01)."""
        v = v.strip().upper()
        if len(v) < 2:
            raise ValueError(f"Invalid well format: {v}")

        row_letter = v[0]
        col_part = v[1:]

        if not ("A" <= row_letter <= "P"):
            raise ValueError(f"Invalid row letter (must be A-P): {row_letter}")

        try:
            col_num = int(col_part)
            if not (1 <= col_num <= 48):
                raise ValueError(f"Invalid column number (must be 1-48): {col_num}")
            return f"{row_letter}{col_num:02d}"
        except ValueError:
            raise ValueError(f"Invalid well format: {v}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert AssayCondition to a flat dictionary for upload/export.

        Returns:
            Dictionary with Plate, Well, and all condition fields
        """
        return {"Plate": self.plate, "Well": self.well, **self.conditions}


class ReferenceSheet(BaseModel):
    """Reference sheet data (sheets starting with '_')."""

    name: str = Field(..., description="Sheet name (including '_' prefix)")
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value pairs from reference sheet",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "_Organisms",
                "data": {
                    "Human": "Homo sapiens",
                    "Mouse": "Mus musculus",
                },
            }
        }
    )


class MIHCSMEMetadata(BaseModel):
    """Complete MIHCSME metadata structure."""

    investigation_information: Optional[InvestigationInformation] = None
    study_information: Optional[StudyInformation] = None
    assay_information: Optional[AssayInformation] = None
    assay_conditions: List[AssayCondition] = Field(default_factory=list)
    reference_sheets: List[ReferenceSheet] = Field(default_factory=list)

    def to_omero_dict(self, namespace_base: str = "MIHCSME") -> Dict[str, Any]:
        """
        Convert the Pydantic model to dictionary format for OMERO upload.

        Args:
            namespace_base: Base namespace for OMERO annotations

        Returns:
            Dictionary in the format expected by the OMERO upload function
        """
        result: Dict[str, Any] = {}

        # Convert Investigation Information
        if self.investigation_information:
            result["InvestigationInformation"] = self.investigation_information.groups

        # Convert Study Information
        if self.study_information:
            result["StudyInformation"] = self.study_information.groups

        # Convert Assay Information
        if self.assay_information:
            result["AssayInformation"] = self.assay_information.groups

        # Convert Assay Conditions to list of dicts using to_dict()
        if self.assay_conditions:
            result["AssayConditions"] = [c.to_dict() for c in self.assay_conditions]

        # Add reference sheets
        for ref_sheet in self.reference_sheets:
            result[ref_sheet.name] = ref_sheet.data

        return result

    @classmethod
    def from_omero_dict(cls, data: Dict[str, Any]) -> "MIHCSMEMetadata":
        """
        Create a MIHCSMEMetadata instance from OMERO dictionary format.

        Args:
            data: Dictionary in OMERO format

        Returns:
            MIHCSMEMetadata instance
        """
        investigation_info = None
        if "InvestigationInformation" in data:
            investigation_info = InvestigationInformation.from_groups_dict(
                data["InvestigationInformation"]
            )

        study_info = None
        if "StudyInformation" in data:
            study_info = StudyInformation.from_groups_dict(data["StudyInformation"])

        assay_info = None
        if "AssayInformation" in data:
            assay_info = AssayInformation.from_groups_dict(data["AssayInformation"])

        assay_conditions = []
        if "AssayConditions" in data and isinstance(data["AssayConditions"], list):
            for condition_dict in data["AssayConditions"]:
                plate = condition_dict.pop("Plate", "")
                well = condition_dict.pop("Well", "")
                # All remaining fields go into conditions
                assay_conditions.append(
                    AssayCondition(plate=plate, well=well, conditions=condition_dict)
                )

        reference_sheets = []
        for key, value in data.items():
            if key.startswith("_") and isinstance(value, dict):
                reference_sheets.append(ReferenceSheet(name=key, data=value))

        return cls(
            investigation_information=investigation_info,
            study_information=study_info,
            assay_information=assay_info,
            assay_conditions=assay_conditions,
            reference_sheets=reference_sheets,
        )

    def to_dataframe(self) -> "pd.DataFrame":
        """
        Convert assay conditions to a pandas DataFrame.

        All condition fields (both standard and custom) are included as columns.

        Returns:
            DataFrame with columns: Plate, Well, and all condition fields
        """
        import pandas as pd

        if not self.assay_conditions:
            return pd.DataFrame()

        conditions_data = [condition.to_dict() for condition in self.assay_conditions]
        return pd.DataFrame(conditions_data)

    def update_conditions_from_dataframe(self, df: "pd.DataFrame") -> "MIHCSMEMetadata":
        """
        Update assay conditions from a DataFrame while preserving other metadata.

        This is a convenience method that creates a new MIHCSMEMetadata instance
        with updated assay conditions from the DataFrame, while preserving all
        other metadata (investigation_information, study_information, etc.) from
        the current instance.

        Args:
            df: DataFrame with at minimum 'Plate' and 'Well' columns.
                All other columns become condition fields.

        Returns:
            New MIHCSMEMetadata instance with updated conditions

        Example:
            >>> df = metadata.to_dataframe()
            >>> df['New Column'] = df['Old Column'].str.lower()
            >>> updated = metadata.update_conditions_from_dataframe(df)
            >>> # updated has the new column, plus all original metadata
        """
        return self.from_dataframe(
            df,
            investigation_information=self.investigation_information,
            study_information=self.study_information,
            assay_information=self.assay_information,
            reference_sheets=self.reference_sheets,
        )

    @classmethod
    def from_dataframe(cls, df: "pd.DataFrame", **kwargs) -> "MIHCSMEMetadata":
        """
        Create MIHCSMEMetadata from a pandas DataFrame of assay conditions.

        Args:
            df: DataFrame with at minimum 'Plate' and 'Well' columns.
                All other columns become condition fields in the conditions dict.
            **kwargs: Additional fields for MIHCSMEMetadata (investigation_information, etc.)

        Returns:
            MIHCSMEMetadata instance with assay conditions from DataFrame

        Example:
            >>> import pandas as pd
            >>> df = pd.DataFrame({
            ...     "Plate": ["Plate1", "Plate1"],
            ...     "Well": ["A01", "A02"],
            ...     "Treatment": ["DMSO", "Drug"],
            ...     "Dose": ["0.1", "10"],
            ...     "DoseUnit": ["µM", "µM"],
            ... })
            >>> metadata = MIHCSMEMetadata.from_dataframe(df)
        """
        import pandas as pd

        if df.empty:
            return cls(assay_conditions=[], **kwargs)

        # Check required columns
        if "Plate" not in df.columns:
            raise ValueError("DataFrame must have a 'Plate' column")
        if "Well" not in df.columns:
            raise ValueError("DataFrame must have a 'Well' column")

        assay_conditions = []
        for _, row in df.iterrows():
            # Build condition dict with all columns except Plate and Well
            conditions = {}
            for col in df.columns:
                if col in ["Plate", "Well"]:
                    continue  # Skip Plate and Well

                value = row[col]
                # Skip NaN/None values
                if pd.isna(value):
                    continue

                # Convert all values to strings
                conditions[col] = str(value) if not isinstance(value, str) else value

            # Create AssayCondition
            assay_conditions.append(
                AssayCondition(
                    plate=str(row["Plate"]),
                    well=str(row["Well"]),
                    conditions=conditions,
                )
            )

        return cls(assay_conditions=assay_conditions, **kwargs)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "investigation_information": {
                    "groups": {
                        "Investigation": {
                            "Investigation Identifier": "INV-001",
                        }
                    }
                },
                "assay_conditions": [
                    {
                        "plate": "Plate1",
                        "well": "A01",
                        "conditions": {"Compound": "DMSO"},
                    }
                ],
            }
        }
    )
