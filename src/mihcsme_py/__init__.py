"""MIHCSME OMERO: Convert MIHCSME metadata from Excel to Pydantic models and upload to OMERO."""

__version__ = "0.1.0"

from mihcsme_py.models import (
    AssayCondition,
    AssayInformation,
    InvestigationInformation,
    MIHCSMEMetadata,
    StudyInformation,
)
from mihcsme_py.omero_connection import connect
from mihcsme_py.parser import parse_excel_to_model
from mihcsme_py.uploader import download_metadata_from_omero, upload_metadata_to_omero

__all__ = [
    "__version__",
    "AssayCondition",
    "AssayInformation",
    "InvestigationInformation",
    "MIHCSMEMetadata",
    "StudyInformation",
    "connect",
    "parse_excel_to_model",
    "upload_metadata_to_omero",
    "download_metadata_from_omero",
]
