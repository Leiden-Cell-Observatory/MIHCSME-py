"""Pydantic models for MIHCSME metadata structure."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class InvestigationInformation(BaseModel):
    """Investigation-level metadata organized by annotation groups."""

    groups: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Nested dictionary: {group_name: {key: value}}",
    )

    class Config:
        extra = "allow"
        json_schema_extra = {
            "example": {
                "groups": {
                    "Investigation": {
                        "Investigation Identifier": "INV-001",
                        "Investigation Title": "Example Investigation",
                    }
                }
            }
        }


class StudyInformation(BaseModel):
    """Study-level metadata organized by annotation groups."""

    groups: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Nested dictionary: {group_name: {key: value}}",
    )

    class Config:
        extra = "allow"
        json_schema_extra = {
            "example": {
                "groups": {
                    "Study": {
                        "Study Identifier": "STD-001",
                        "Study Title": "Example Study",
                    }
                }
            }
        }


class AssayInformation(BaseModel):
    """Assay-level metadata organized by annotation groups."""

    groups: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Nested dictionary: {group_name: {key: value}}",
    )

    class Config:
        extra = "allow"
        json_schema_extra = {
            "example": {
                "groups": {
                    "Assay": {
                        "Assay Identifier": "ASY-001",
                        "Assay Technology Type": "Microscopy",
                    }
                }
            }
        }


class AssayCondition(BaseModel):
    """Single well condition from AssayConditions sheet."""

    plate: str = Field(..., description="Plate identifier/name")
    well: str = Field(..., description="Well identifier (e.g., A01, B12)")
    conditions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata fields for this well",
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

    class Config:
        json_schema_extra = {
            "example": {
                "plate": "Plate1",
                "well": "A01",
                "conditions": {
                    "Compound": "DMSO",
                    "Concentration": "0.1%",
                },
            }
        }


class ReferenceSheet(BaseModel):
    """Reference sheet data (sheets starting with '_')."""

    name: str = Field(..., description="Sheet name (including '_' prefix)")
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value pairs from reference sheet",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "_Organisms",
                "data": {
                    "Human": "Homo sapiens",
                    "Mouse": "Mus musculus",
                },
            }
        }


class MIHCSMEMetadata(BaseModel):
    """Complete MIHCSME metadata structure."""

    investigation_information: Optional[InvestigationInformation] = None
    study_information: Optional[StudyInformation] = None
    assay_information: Optional[AssayInformation] = None
    assay_conditions: List[AssayCondition] = Field(default_factory=list)
    reference_sheets: List[ReferenceSheet] = Field(default_factory=list)

    def to_omero_dict(self, namespace_base: str = "MIHCSME") -> Dict[str, Any]:
        """
        Convert the Pydantic model to the legacy dictionary format for OMERO upload.

        Args:
            namespace_base: Base namespace for OMERO annotations

        Returns:
            Dictionary in the format expected by the legacy upload function
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

        # Convert Assay Conditions to list of dicts
        if self.assay_conditions:
            conditions_list = []
            for condition in self.assay_conditions:
                condition_dict = {
                    "Plate": condition.plate,
                    "Well": condition.well,
                    **condition.conditions,
                }
                conditions_list.append(condition_dict)
            result["AssayConditions"] = conditions_list

        # Add reference sheets
        for ref_sheet in self.reference_sheets:
            result[ref_sheet.name] = ref_sheet.data

        return result

    @classmethod
    def from_omero_dict(cls, data: Dict[str, Any]) -> "MIHCSMEMetadata":
        """
        Create a MIHCSMEMetadata instance from the legacy dictionary format.

        Args:
            data: Dictionary in the legacy format

        Returns:
            MIHCSMEMetadata instance
        """
        investigation_info = None
        if "InvestigationInformation" in data:
            investigation_info = InvestigationInformation(groups=data["InvestigationInformation"])

        study_info = None
        if "StudyInformation" in data:
            study_info = StudyInformation(groups=data["StudyInformation"])

        assay_info = None
        if "AssayInformation" in data:
            assay_info = AssayInformation(groups=data["AssayInformation"])

        assay_conditions = []
        if "AssayConditions" in data and isinstance(data["AssayConditions"], list):
            for condition_dict in data["AssayConditions"]:
                plate = condition_dict.get("Plate", "")
                well = condition_dict.get("Well", "")
                # Extract all other fields as conditions
                conditions = {
                    k: v for k, v in condition_dict.items() if k not in ["Plate", "Well"]
                }
                assay_conditions.append(
                    AssayCondition(plate=plate, well=well, conditions=conditions)
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

    class Config:
        json_schema_extra = {
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
