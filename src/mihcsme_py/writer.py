"""Write MIHCSME metadata to Excel format."""

from copy import copy
from pathlib import Path
from typing import Dict, List, Any, Union, BinaryIO

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.worksheet.worksheet import Worksheet

from mihcsme_py.models import MIHCSMEMetadata

# Default condition column headers written when AssayConditions sheet is empty
DEFAULT_CONDITION_KEYS = ["Treatment", "Concentration", "Unit", "CellLine", "TimeTreatment", "RepID"]


def write_metadata_to_excel(
    metadata: MIHCSMEMetadata, output_path: Union[Path, BinaryIO]
) -> None:
    """
    Write MIHCSME metadata to Excel file.

    All sheets are always written, even if empty, so the file can be used as
    a template. The AssayConditions sheet uses default column headers when no
    conditions are present.

    :param metadata: MIHCSMEMetadata object to export
    :param output_path: Path to output Excel file, or a file-like object (e.g., BytesIO)
    """
    wb = Workbook()
    # Remove default sheet
    if "Sheet" in wb.sheetnames:
        wb.remove(wb["Sheet"])

    # Write Investigation Information (always)
    groups = metadata.investigation_information.groups if metadata.investigation_information else {}
    _write_grouped_sheet(
        wb,
        "InvestigationInformation",
        groups,
        header_comment="# Investigation Information - Metadata about the overall investigation"
    )

    # Write Study Information (always)
    groups = metadata.study_information.groups if metadata.study_information else {}
    _write_grouped_sheet(
        wb,
        "StudyInformation",
        groups,
        header_comment="# Study Information - Metadata about the study design"
    )

    # Write Assay Information (always)
    groups = metadata.assay_information.groups if metadata.assay_information else {}
    _write_grouped_sheet(
        wb,
        "AssayInformation",
        groups,
        header_comment="# Assay Information - Metadata about the assay protocol"
    )

    # Write Assay Conditions (always)
    _write_assay_conditions(wb, metadata.assay_conditions)

    # Write Reference Sheets
    for ref_sheet in metadata.reference_sheets:
        _write_reference_sheet(wb, ref_sheet.name, ref_sheet.data)

    # Save workbook
    wb.save(output_path)


def _write_grouped_sheet(
    wb: Workbook,
    sheet_name: str,
    groups: Dict[str, Dict[str, str]],
    header_comment: str = None
) -> None:
    """
    Write a grouped metadata sheet (Investigation/Study/Assay Information).

    :param wb: Workbook object
    :param sheet_name: Name of the sheet
    :param groups: Dictionary of groups {group_name: {key: value}}
    :param header_comment: Optional comment to add at the top
    """
    ws = wb.create_sheet(sheet_name)

    # Add header comment if provided
    row_num = 1
    if header_comment:
        ws.cell(row=row_num, column=1, value=header_comment)
        ws.cell(row=row_num, column=1).font = Font(italic=True, color="808080")
        row_num += 1

    # Add column headers
    ws.cell(row=row_num, column=1, value="Group")
    ws.cell(row=row_num, column=2, value="Key")
    ws.cell(row=row_num, column=3, value="Value")

    # Style headers
    for col in range(1, 4):
        cell = ws.cell(row=row_num, column=col)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")

    row_num += 1

    # Write data
    for group_name, group_data in groups.items():
        for key, value in group_data.items():
            ws.cell(row=row_num, column=1, value=group_name)
            ws.cell(row=row_num, column=2, value=key)
            ws.cell(row=row_num, column=3, value=value)
            row_num += 1

    # Adjust column widths
    ws.column_dimensions['A'].width = 25
    ws.column_dimensions['B'].width = 35
    ws.column_dimensions['C'].width = 50


def _write_assay_conditions(wb: Workbook, assay_conditions: List[Any]) -> None:
    """
    Write AssayConditions sheet.

    When no conditions are provided, a blank template with default column
    headers is written so users can fill it in manually.

    :param wb: Workbook object
    :param assay_conditions: List of AssayCondition objects (may be empty)
    """
    from openpyxl.utils import get_column_letter

    ws = wb.create_sheet("AssayConditions")

    # Add header comment
    ws.cell(row=1, column=1, value="# Assay Conditions - Per-well metadata")
    ws.cell(row=1, column=1).font = Font(italic=True, color="808080")

    # Collect condition keys from data, or fall back to defaults
    if assay_conditions:
        all_keys: set = set()
        for condition in assay_conditions:
            all_keys.update(condition.conditions.keys())
        condition_keys = sorted(all_keys)
    else:
        condition_keys = list(DEFAULT_CONDITION_KEYS)

    # Write headers
    headers = ["Plate", "Well"] + condition_keys
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=2, column=col_idx, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")

    # Write data rows
    for row_idx, condition in enumerate(assay_conditions, start=3):
        ws.cell(row=row_idx, column=1, value=condition.plate)
        ws.cell(row=row_idx, column=2, value=condition.well)

        for col_idx, key in enumerate(condition_keys, start=3):
            value = condition.conditions.get(key, "")
            ws.cell(row=row_idx, column=col_idx, value=value)

    # Adjust column widths
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 10
    for col_idx in range(3, 3 + len(condition_keys)):
        ws.column_dimensions[get_column_letter(col_idx)].width = 20


def _write_reference_sheet(wb: Workbook, sheet_name: str, data: Dict[str, Any]) -> None:
    """
    Write a reference sheet (sheets starting with _).

    :param wb: Workbook object
    :param sheet_name: Name of the reference sheet
    :param data: Dictionary of key-value pairs
    """
    # Ensure sheet name starts with underscore
    if not sheet_name.startswith('_'):
        sheet_name = f'_{sheet_name}'

    ws = wb.create_sheet(sheet_name)

    if not data:
        # Empty reference sheet
        ws.cell(row=1, column=1, value="# Empty reference sheet")
        return

    # Write headers
    headers = ["Key", "Value"]
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")

    # Write data as key-value pairs
    for row_idx, (key, value) in enumerate(data.items(), start=2):
        ws.cell(row=row_idx, column=1, value=key)
        ws.cell(row=row_idx, column=2, value=value)

    # Adjust column widths
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 50


# ---------------------------------------------------------------------------
# Fill the official MIHCSME Excel template
# ---------------------------------------------------------------------------

DEFAULT_TEMPLATE_PATH = Path(__file__).parent / "templates" / "LEI-MIHCSME.xlsx"

# Model group names that differ from the group names used in the template
_TEMPLATE_GROUP_ALIASES = {"InvestigationInfo": "InvestigationInformation"}


def fill_template(
    metadata: MIHCSMEMetadata,
    output_path: Union[Path, BinaryIO],
    template_path: Union[str, Path, None] = None,
) -> None:
    """
    Write MIHCSME metadata into the official MIHCSME Excel template.

    Unlike :func:`write_metadata_to_excel`, this keeps the full template layout:
    every field (also empty ones), the descriptions/examples column, the
    dropdown validations and the ontology reference sheets.

    - Values are written into the Value column of matching (group, key) rows.
      Value cells of template rows without metadata are cleared.
    - Fields not present in the template are appended below the existing rows.
    - Data collaborators fill the template's collaborator rows in order; extra
      collaborators are appended.
    - AssayConditions keeps the template columns; extra condition keys are added
      as new columns and existing data rows are replaced.

    :param metadata: MIHCSMEMetadata object to export
    :param output_path: Path to output Excel file, or a file-like object (e.g., BytesIO)
    :param template_path: Optional custom template; defaults to the bundled
        LEI-MIHCSME template
    """
    template = Path(template_path) if template_path else DEFAULT_TEMPLATE_PATH
    wb = load_workbook(template)

    sections = {
        "InvestigationInformation": metadata.investigation_information,
        "StudyInformation": metadata.study_information,
        "AssayInformation": metadata.assay_information,
    }
    for sheet_name, section in sections.items():
        if sheet_name not in wb.sheetnames:
            raise ValueError(f"Template is missing required sheet '{sheet_name}'")
        groups = section.groups if section else {}
        _fill_grouped_sheet(wb[sheet_name], groups)

    if "AssayConditions" not in wb.sheetnames:
        raise ValueError("Template is missing required sheet 'AssayConditions'")
    _fill_assay_conditions(wb["AssayConditions"], metadata.assay_conditions)

    wb.save(output_path)


def _normalize_key(key: Any) -> str:
    """Normalize a key for matching (template keys contain stray double spaces)."""
    return " ".join(str(key).split()).lower()


def _fill_grouped_sheet(ws: Worksheet, groups: Dict[str, Dict[str, Any]]) -> None:
    """Fill the Value column of a grouped template sheet."""
    # Pending values per (group, normalized key); collaborators are kept as a list
    pending: Dict[tuple, Any] = {}
    collaborators: List[Any] = []
    for group_name, group_data in groups.items():
        template_group = _TEMPLATE_GROUP_ALIASES.get(group_name, group_name)
        for key, value in group_data.items():
            if template_group == "DataCollaborator":
                collaborators.append(value)
            else:
                pending[(template_group, _normalize_key(key))] = (key, value)

    header_row = None
    last_row = 0
    collaborator_key = "ORCID  Data Collaborator"
    for row in range(1, ws.max_row + 1):
        group = ws.cell(row=row, column=1).value
        key = ws.cell(row=row, column=2).value
        if group == "Annotation_groups":
            header_row = row
            last_row = row
            continue
        if header_row is None or group is None or key is None or str(group).startswith("#"):
            continue

        last_row = row
        value_cell = ws.cell(row=row, column=3)
        if group == "DataCollaborator":
            collaborator_key = key
            value_cell.value = collaborators.pop(0) if collaborators else None
        else:
            match = pending.pop((group, _normalize_key(key)), None)
            value_cell.value = match[1] if match else None

    if header_row is None:
        raise ValueError(f"Template sheet '{ws.title}' has no 'Annotation_groups' header row")

    # Append fields that have no row in the template
    extra_rows = [("DataCollaborator", collaborator_key, v) for v in collaborators]
    extra_rows += [(group, key, value) for (group, _), (key, value) in pending.items()]
    for offset, (group, key, value) in enumerate(extra_rows, start=1):
        ws.cell(row=last_row + offset, column=1, value=group)
        ws.cell(row=last_row + offset, column=2, value=key)
        ws.cell(row=last_row + offset, column=3, value=value)


def _fill_assay_conditions(ws: Worksheet, assay_conditions: List[Any]) -> None:
    """Fill the AssayConditions sheet below the template's header row."""
    header_row = None
    for row in range(1, ws.max_row + 1):
        first = ws.cell(row=row, column=1).value
        if first is not None and not str(first).startswith("#"):
            header_row = row
            break
    if header_row is None:
        raise ValueError("Template sheet 'AssayConditions' has no header row")

    headers = [
        ws.cell(row=header_row, column=col).value for col in range(1, ws.max_column + 1)
    ]
    while headers and headers[-1] is None:
        headers.pop()
    if headers[:2] != ["Plate", "Well"]:
        raise ValueError("Template AssayConditions header must start with 'Plate', 'Well'")

    # Add condition keys missing from the template as new columns
    extra_keys = sorted(
        {key for condition in assay_conditions for key in condition.conditions} - set(headers)
    )
    header_style_cell = ws.cell(row=header_row, column=len(headers))
    for key in extra_keys:
        headers.append(key)
        cell = ws.cell(row=header_row, column=len(headers), value=key)
        cell.font = copy(header_style_cell.font)
        cell.fill = copy(header_style_cell.fill)

    # Replace any existing data rows
    if ws.max_row > header_row:
        ws.delete_rows(header_row + 1, ws.max_row - header_row)

    for row_idx, condition in enumerate(assay_conditions, start=header_row + 1):
        ws.cell(row=row_idx, column=1, value=condition.plate)
        ws.cell(row=row_idx, column=2, value=condition.well)
        for col_idx, key in enumerate(headers[2:], start=3):
            value = condition.conditions.get(key)
            if value is not None:
                ws.cell(row=row_idx, column=col_idx, value=value)
