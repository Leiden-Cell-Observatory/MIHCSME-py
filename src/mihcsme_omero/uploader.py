"""Upload MIHCSME metadata to OMERO using omero-py directly."""

import logging
from typing import Any, Dict, Literal

import pandas as pd
from omero.gateway import BlitzGateway

from mihcsme_omero.models import MIHCSMEMetadata
from mihcsme_omero.omero_connection import (
    create_map_annotation,
    delete_annotations_from_object,
    get_wells_from_plate,
)

logger = logging.getLogger(__name__)

# Default namespace
DEFAULT_NS_BASE = "MIHCSME"

# Sheet name constants
SHEET_INVESTIGATION = "InvestigationInformation"
SHEET_STUDY = "StudyInformation"
SHEET_ASSAY = "AssayInformation"
SHEET_CONDITIONS = "AssayConditions"


def upload_metadata_to_omero(
    conn: BlitzGateway,
    metadata: MIHCSMEMetadata,
    target_type: Literal["Screen", "Plate"],
    target_id: int,
    namespace: str = DEFAULT_NS_BASE,
    replace: bool = False,
) -> Dict[str, Any]:
    """
    Upload MIHCSME metadata to OMERO from a Pydantic model.

    Args:
        conn: Active OMERO connection (BlitzGateway)
        metadata: MIHCSMEMetadata Pydantic model instance
        target_type: Type of target object ("Screen" or "Plate")
        target_id: ID of the target OMERO object
        namespace: Base namespace for annotations (default: "MIHCSME")
        replace: If True, remove existing annotations before uploading

    Returns:
        Dictionary with upload summary:
            - status: 'success', 'partial_success', or 'error'
            - message: Human-readable message
            - wells_processed: Number of wells processed
            - wells_succeeded: Number of wells successfully annotated
            - wells_failed: Number of wells that failed
            - removed_annotations: Number of annotations removed (if replace=True)

    Raises:
        ValueError: If target_type is not 'Screen' or 'Plate'
    """
    summary = {
        "status": "error",
        "message": "Initialization failed",
        "target_type": target_type,
        "target_id": target_id,
        "wells_processed": 0,
        "wells_succeeded": 0,
        "wells_failed": 0,
        "removed_annotations": 0,
    }

    if target_type not in ["Screen", "Plate"]:
        summary["message"] = (
            f"This function only supports 'Screen' or 'Plate' as target object types, "
            f"not '{target_type}'."
        )
        logger.error(summary["message"])
        return summary

    processed_ok = True

    try:
        # If replace=True, remove existing annotations first
        if replace:
            logger.info(f"Replacing existing metadata for {target_type} {target_id}...")
            removal_count = _remove_metadata_recursive(conn, target_type, target_id, namespace)
            summary["removed_annotations"] = removal_count
            logger.info(f"Removed {removal_count} existing annotations")

        # 1. Apply Object-Level Metadata (Screen or Plate level)
        logger.info(f"--- Applying Metadata to {target_type} {target_id} ---")

        # Apply Investigation Information
        if metadata.investigation_information:
            processed_ok &= _apply_grouped_metadata(
                conn,
                target_type,
                target_id,
                metadata.investigation_information.groups,
                f"{namespace}/{SHEET_INVESTIGATION}",
            )

        # Apply Study Information
        if metadata.study_information:
            processed_ok &= _apply_grouped_metadata(
                conn,
                target_type,
                target_id,
                metadata.study_information.groups,
                f"{namespace}/{SHEET_STUDY}",
            )

        # Apply Assay Information
        if metadata.assay_information:
            processed_ok &= _apply_grouped_metadata(
                conn,
                target_type,
                target_id,
                metadata.assay_information.groups,
                f"{namespace}/{SHEET_ASSAY}",
            )

        # 2. Apply Well-Level Metadata
        logger.info("--- Applying Well-Level Metadata (AssayConditions) ---")

        if not metadata.assay_conditions:
            logger.warning("No assay conditions to upload")
        else:
            # Convert to DataFrame for easier processing
            conditions_data = []
            for condition in metadata.assay_conditions:
                row_data = {
                    "Plate": condition.plate,
                    "Well": condition.well,
                    **condition.conditions,
                }
                conditions_data.append(row_data)

            assay_conditions_df = pd.DataFrame(conditions_data)
            ns_conditions = f"{namespace}/{SHEET_CONDITIONS}"

            # Get plates to process
            plates = _get_plates_to_process(conn, target_type, target_id)

            if not plates:
                logger.warning(f"No plates found for {target_type} ID {target_id}")
            else:
                logger.info(f"Found {len(plates)} plate(s) to process")
                total_well_success = 0
                total_well_fail = 0

                for plate in plates:
                    plate_id = plate.getId()
                    plate_identifier = plate.getName()
                    logger.debug(f"Processing Plate ID: {plate_id}, Name: '{plate_identifier}'")

                    s, f = _apply_assay_conditions_to_wells(
                        conn, plate_id, plate_identifier, assay_conditions_df, ns_conditions
                    )
                    total_well_success += s
                    total_well_fail += f

                summary["wells_succeeded"] = total_well_success
                summary["wells_failed"] = total_well_fail
                summary["wells_processed"] = total_well_success + total_well_fail
                logger.info(
                    f"Well metadata summary: Processed={summary['wells_processed']}, "
                    f"Success={total_well_success}, Failures={total_well_fail}"
                )

        # Determine final status
        if processed_ok:
            summary["status"] = "success"
            if replace:
                summary["message"] = (
                    f"Metadata replaced successfully: removed {summary['removed_annotations']} "
                    f"old annotations, applied new metadata."
                )
            else:
                summary["message"] = "Annotations applied successfully."
        else:
            summary["status"] = "partial_success"
            summary["message"] = (
                f"Some {target_type.lower()}-level annotations may have failed (check logs)."
            )

        logger.info(f"Annotation process finished for {target_type} {target_id}")

    except Exception as e:
        summary["message"] = f"An unexpected error occurred during annotation: {e}"
        logger.error(summary["message"], exc_info=True)
        summary["status"] = "error"

    return summary


def _apply_grouped_metadata(
    conn: BlitzGateway,
    obj_type: str,
    obj_id: int,
    groups: Dict[str, Dict[str, Any]],
    base_namespace: str,
) -> bool:
    """
    Apply grouped metadata (e.g., Investigation/Study/Assay Information).

    Args:
        conn: OMERO connection
        obj_type: Object type
        obj_id: Object ID
        groups: Nested dictionary {group_name: {key: value}}
        base_namespace: Base namespace

    Returns:
        True if all successful, False otherwise
    """
    if not groups:
        logger.debug(f"No grouped metadata for {obj_type} {obj_id}")
        return True

    success = True

    for group_name, group_data in groups.items():
        if not isinstance(group_data, dict):
            logger.warning(f"Group '{group_name}' data is not a dictionary, skipping")
            continue

        # Filter out None/NaN values
        kv_pairs = {str(k): str(v) for k, v in group_data.items() if v is not None and pd.notna(v)}

        if not kv_pairs:
            logger.debug(f"Group '{group_name}' is empty after filtering, skipping")
            continue

        # Create namespace for this group
        group_namespace = f"{base_namespace}/{group_name}"

        try:
            ann_id = create_map_annotation(conn, obj_type, obj_id, kv_pairs, group_namespace)
            if ann_id:
                logger.debug(
                    f"Applied group '{group_name}' metadata (Annotation ID: {ann_id})"
                )
            else:
                logger.error(f"Failed to apply group '{group_name}' metadata")
                success = False
        except Exception as e:
            logger.error(f"Error applying group '{group_name}' metadata: {e}")
            success = False

    return success


def _get_plates_to_process(
    conn: BlitzGateway, target_type: str, target_id: int
) -> list:
    """Get list of plates to process based on target type."""
    if target_type == "Screen":
        screen = conn.getObject("Screen", target_id)
        if not screen:
            logger.warning(f"Could not retrieve Screen object for ID {target_id}")
            return []
        return list(screen.listChildren())
    else:  # Plate
        plate = conn.getObject("Plate", target_id)
        if not plate:
            logger.warning(f"Could not retrieve Plate object for ID {target_id}")
            return []
        return [plate]


def _apply_assay_conditions_to_wells(
    conn: BlitzGateway,
    plate_id: int,
    plate_identifier: str,
    assay_conditions_df: pd.DataFrame,
    namespace: str,
) -> tuple:
    """
    Apply AssayConditions metadata to wells.

    Returns:
        Tuple of (success_count, fail_count)
    """
    logger.info(f"Processing Wells for Plate ID: {plate_id} (Identifier: '{plate_identifier}')")
    success_count = 0
    fail_count = 0

    # Filter metadata for this plate
    try:
        assay_conditions_df["Plate"] = assay_conditions_df["Plate"].astype(str)
        plate_metadata = assay_conditions_df[
            assay_conditions_df["Plate"] == str(plate_identifier)
        ].copy()

        if plate_metadata.empty:
            logger.warning(
                f"No metadata found for Plate identifier '{plate_identifier}' in AssayConditions"
            )
            wells = get_wells_from_plate(conn, plate_id)
            return 0, len(wells)

        if "Well" not in plate_metadata.columns:
            logger.error(f"Missing 'Well' column for Plate '{plate_identifier}'")
            wells = get_wells_from_plate(conn, plate_id)
            return 0, len(wells)

        # Create metadata lookup by normalized well name
        metadata_lookup = {}
        for _, row in plate_metadata.iterrows():
            well_name = _normalize_well_name(str(row["Well"]))
            if well_name:
                # Exclude 'Plate' and 'Well' columns
                well_metadata = {
                    str(k): str(v)
                    for k, v in row.items()
                    if k not in ["Plate", "Well"] and pd.notna(v)
                }
                metadata_lookup[well_name] = well_metadata

        logger.debug(
            f"Metadata contains {len(metadata_lookup)} wells: {sorted(metadata_lookup.keys())}"
        )

    except Exception as e:
        logger.error(f"Error filtering metadata for Plate '{plate_identifier}': {e}")
        return 0, 0

    # Get wells from OMERO
    try:
        wells = get_wells_from_plate(conn, plate_id)
        if not wells:
            logger.warning(f"No wells found in OMERO Plate ID {plate_id}")
            return 0, len(metadata_lookup)

        logger.debug(f"OMERO contains {len(wells)} wells")

    except Exception as e:
        logger.error(f"Error retrieving wells for Plate ID {plate_id}: {e}")
        return 0, len(metadata_lookup)

    # Match metadata to wells
    processed_well_names = set()
    metadata_wells = set(metadata_lookup.keys())

    for well in wells:
        row = well.row
        col = well.column
        well_id = well.getId()
        # Normalize to A01 format
        well_name = f"{chr(ord('A') + row)}{col + 1:02d}"
        processed_well_names.add(well_name)

        if well_name in metadata_lookup:
            well_metadata = metadata_lookup[well_name]

            if not well_metadata:
                logger.debug(f"Metadata for Well '{well_name}' empty, skipping")
                success_count += 1
                continue

            # Apply metadata to the well
            try:
                ann_id = create_map_annotation(conn, "Well", well_id, well_metadata, namespace)
                if ann_id:
                    logger.debug(
                        f"  Applied metadata to Well ID {well_id} (Name: {well_name}, "
                        f"Row: {row}, Col: {col})"
                    )
                    success_count += 1
                else:
                    logger.error(f"  Failed to apply metadata to Well ID {well_id}")
                    fail_count += 1
            except Exception as e:
                logger.error(f"  Error applying metadata to Well ID {well_id}: {e}")
                fail_count += 1
        else:
            logger.warning(
                f"  No metadata found for Well '{well_name}' (ID: {well_id}) "
                f"in Plate '{plate_identifier}'"
            )
            fail_count += 1

    # Check for extra metadata wells
    extra_metadata = metadata_wells - processed_well_names
    if extra_metadata:
        logger.warning(
            f"  Metadata found for wells not in OMERO Plate {plate_id}: "
            f"{', '.join(sorted(list(extra_metadata)))}"
        )
        fail_count += len(extra_metadata)

    logger.info(
        f"Plate {plate_id} ('{plate_identifier}') processing complete. "
        f"Success: {success_count}, Failures: {fail_count}"
    )
    return success_count, fail_count


def _normalize_well_name(well_name: str) -> str:
    """Normalize well names to zero-padded format (A01)."""
    if not well_name:
        return ""

    well_name = well_name.strip().upper()
    if len(well_name) < 2:
        return ""

    row_letter = well_name[0]
    col_part = well_name[1:]

    try:
        col_num = int(col_part)
        return f"{row_letter}{col_num:02d}"
    except ValueError:
        return ""


def _remove_metadata_recursive(
    conn: BlitzGateway, target_type: str, target_id: int, namespace: str
) -> int:
    """
    Recursively remove metadata from target and all children.

    Returns:
        Total number of annotations removed
    """
    total_removed = 0

    # Remove from target object
    total_removed += delete_annotations_from_object(conn, target_type, target_id, namespace)

    # If Screen, process plates and wells
    if target_type == "Screen":
        screen = conn.getObject("Screen", target_id)
        if screen:
            for plate in screen.listChildren():
                plate_id = plate.getId()
                total_removed += delete_annotations_from_object(conn, "Plate", plate_id, namespace)

                # Remove from wells
                for well in plate.listChildren():
                    well_id = well.getId()
                    total_removed += delete_annotations_from_object(
                        conn, "Well", well_id, namespace
                    )

    # If Plate, process wells
    elif target_type == "Plate":
        plate = conn.getObject("Plate", target_id)
        if plate:
            for well in plate.listChildren():
                well_id = well.getId()
                total_removed += delete_annotations_from_object(conn, "Well", well_id, namespace)

    return total_removed
