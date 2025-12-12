"""Parse MIHCSME Excel files into Pydantic models."""

import logging
from pathlib import Path
from typing import Union

import pandas as pd

from mihcsme_omero.models import (
    AssayCondition,
    AssayInformation,
    InvestigationInformation,
    MIHCSMEMetadata,
    ReferenceSheet,
    StudyInformation,
)

logger = logging.getLogger(__name__)

# Sheet name constants
SHEET_INVESTIGATION = "InvestigationInformation"
SHEET_STUDY = "StudyInformation"
SHEET_ASSAY = "AssayInformation"
SHEET_CONDITIONS = "AssayConditions"


def parse_excel_to_model(excel_path: Union[str, Path]) -> MIHCSMEMetadata:
    """
    Parse a MIHCSME Excel file into a Pydantic model.

    Args:
        excel_path: Path to the MIHCSME Excel file

    Returns:
        MIHCSMEMetadata instance

    Raises:
        FileNotFoundError: If the Excel file doesn't exist
        ValueError: If required sheets are missing or malformed
    """
    filepath = Path(excel_path)

    if not filepath.exists():
        raise FileNotFoundError(f"Excel file not found: {filepath}")

    if filepath.suffix.lower() not in [".xlsx", ".xls"]:
        raise ValueError(f"File must be Excel format (.xlsx/.xls): {filepath}")

    logger.info(f"Parsing MIHCSME Excel file: {filepath}")

    try:
        xls = pd.ExcelFile(filepath)
        available_sheets = xls.sheet_names

        # Check for required sheets
        required_sheets = [SHEET_INVESTIGATION, SHEET_STUDY, SHEET_ASSAY, SHEET_CONDITIONS]
        missing_sheets = [s for s in required_sheets if s not in available_sheets]
        if missing_sheets:
            raise ValueError(f"Missing required sheets: {', '.join(missing_sheets)}")

        # Parse Investigation Information
        investigation_info = None
        if SHEET_INVESTIGATION in available_sheets:
            investigation_info = _parse_key_value_sheet(xls, SHEET_INVESTIGATION)
            if investigation_info:
                investigation_info = InvestigationInformation(groups=investigation_info)

        # Parse Study Information
        study_info = None
        if SHEET_STUDY in available_sheets:
            study_info = _parse_key_value_sheet(xls, SHEET_STUDY)
            if study_info:
                study_info = StudyInformation(groups=study_info)

        # Parse Assay Information
        assay_info = None
        if SHEET_ASSAY in available_sheets:
            assay_info = _parse_key_value_sheet(xls, SHEET_ASSAY)
            if assay_info:
                assay_info = AssayInformation(groups=assay_info)

        # Parse Assay Conditions
        assay_conditions = []
        if SHEET_CONDITIONS in available_sheets:
            assay_conditions = _parse_assay_conditions(xls, SHEET_CONDITIONS)

        # Parse Reference Sheets
        reference_sheets = []
        for sheet_name in available_sheets:
            if sheet_name.startswith("_"):
                ref_data = _parse_reference_sheet(xls, sheet_name)
                if ref_data:
                    reference_sheets.append(ReferenceSheet(name=sheet_name, data=ref_data))

        xls.close()

        return MIHCSMEMetadata(
            investigation_information=investigation_info,
            study_information=study_info,
            assay_information=assay_info,
            assay_conditions=assay_conditions,
            reference_sheets=reference_sheets,
        )

    except Exception as e:
        logger.error(f"Failed to parse Excel file '{filepath}': {e}")
        raise


def _parse_key_value_sheet(xls: pd.ExcelFile, sheet_name: str) -> dict:
    """
    Parse key-value sheets (Investigation/Study/Assay Information).

    These sheets have three columns: Group, Key, Value
    And are organized into groups.
    """
    logger.debug(f"Parsing key-value sheet: {sheet_name}")

    try:
        df = pd.read_excel(xls, sheet_name=sheet_name)

        # Skip rows that start with '#'
        df = df[~df.iloc[:, 0].astype(str).str.startswith("#")]

        # Convert to nested structure
        sheet_data = {}

        for _, row in df.iterrows():
            # Get the first column which contains the group
            group = row.iloc[0]

            # Skip header rows or empty rows
            if pd.isna(group) or group == "Annotation_groups" or str(group).startswith("#"):
                continue

            # Get key and value (columns 1 and 2)
            if len(row) > 2:
                key = row.iloc[1]
                value = row.iloc[2]
            else:
                continue

            # Skip rows with no key
            if pd.isna(key):
                continue

            # Initialize the group if it doesn't exist
            if group not in sheet_data:
                sheet_data[group] = {}

            # Add the key-value pair to the group
            # Convert NaN to None for cleaner JSON
            sheet_data[group][key] = None if pd.isna(value) else value

        logger.info(f"Parsed '{sheet_name}' with {len(sheet_data)} groups")
        return sheet_data

    except Exception as e:
        logger.error(f"Error parsing key-value sheet '{sheet_name}': {e}")
        raise


def _parse_assay_conditions(xls: pd.ExcelFile, sheet_name: str) -> list:
    """Parse the AssayConditions sheet into a list of AssayCondition models."""
    logger.debug(f"Parsing assay conditions sheet: {sheet_name}")

    try:
        df = pd.read_excel(xls, sheet_name=sheet_name, dtype=str)

        # Skip rows that start with '#'
        df = df[~df.iloc[:, 0].astype(str).str.startswith("#")]

        if df.empty:
            logger.warning(f"No data found in {sheet_name} after removing comments")
            return []

        # The first remaining row is the header
        headers = df.iloc[0].tolist()

        # Check required columns
        if "Plate" not in headers or "Well" not in headers:
            raise ValueError(f"Missing required 'Plate' or 'Well' column in {sheet_name}")

        # Get the data rows
        data_rows = df.iloc[1:].copy()
        data_rows.columns = headers

        # Drop columns with NaN headers
        data_rows = data_rows.loc[:, ~pd.isna(headers)]

        # Convert to AssayCondition models
        assay_conditions = []
        for _, row in data_rows.iterrows():
            plate = row.get("Plate")
            well = row.get("Well")

            if pd.isna(plate) or pd.isna(well):
                continue

            # Extract all other fields as conditions
            conditions = {}
            for col in data_rows.columns:
                if col not in ["Plate", "Well"] and not pd.isna(row[col]):
                    conditions[col] = row[col]

            assay_conditions.append(
                AssayCondition(
                    plate=str(plate),
                    well=str(well),
                    conditions=conditions,
                )
            )

        logger.info(f"Parsed {len(assay_conditions)} assay conditions from '{sheet_name}'")
        return assay_conditions

    except Exception as e:
        logger.error(f"Error parsing assay conditions '{sheet_name}': {e}")
        raise


def _parse_reference_sheet(xls: pd.ExcelFile, sheet_name: str) -> dict:
    """Parse reference sheets (those starting with '_')."""
    logger.debug(f"Parsing reference sheet: {sheet_name}")

    try:
        df = pd.read_excel(xls, sheet_name=sheet_name)

        # Skip rows that start with '#'
        df = df[~df.iloc[:, 0].astype(str).str.startswith("#")]

        # Skip empty rows
        df = df.dropna(how="all")

        if df.empty:
            logger.debug(f"Reference sheet '{sheet_name}' is empty")
            return {}

        # Find the first non-comment row with data
        valid_rows = []
        for idx, row in df.iterrows():
            if not all(pd.isna(val) for val in row):
                valid_rows.append(idx)

        if not valid_rows:
            return {}

        header_row_idx = valid_rows[0]

        # Get data
        headers = df.iloc[header_row_idx].tolist()

        # Check if we have at least two columns
        if len(headers) < 2:
            return {}

        data_rows = df.iloc[header_row_idx + 1 :].copy()
        data_rows.columns = headers

        # Convert to dictionary
        ref_data = {}
        for _, row in data_rows.iterrows():
            # Use first column as key, second as value
            if len(row) >= 2:
                key = row.iloc[0]
                value = row.iloc[1]
                if not pd.isna(key):
                    ref_data[str(key)] = None if pd.isna(value) else value

        logger.info(f"Parsed reference sheet '{sheet_name}' with {len(ref_data)} entries")
        return ref_data

    except Exception as e:
        logger.error(f"Error processing sheet {sheet_name}: {e}")
        return {}
