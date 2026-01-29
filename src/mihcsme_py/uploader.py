"""Upload MIHCSME metadata to OMERO using omero-py directly."""

import logging
from typing import Any, Dict, Literal

import pandas as pd
from omero.gateway import BlitzGateway

from mihcsme_py.models import MIHCSMEMetadata
from mihcsme_py.omero_connection import (
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
        logger.info(f"\n{'=' * 80}")
        logger.info(f"UPLOADING METADATA TO {target_type} (ID: {target_id})")
        logger.info(f"{'=' * 80}")

        # Apply Investigation Information
        if metadata.investigation_information:
            logger.info(f"\n[1/4] Uploading Investigation Information...")
            num_groups = len(metadata.investigation_information.groups)
            logger.info(f"  → {num_groups} group(s) to upload")
            processed_ok &= _apply_grouped_metadata(
                conn,
                target_type,
                target_id,
                metadata.investigation_information.groups,
                f"{namespace}/{SHEET_INVESTIGATION}",
            )
        else:
            logger.info(f"\n[1/4] No Investigation Information to upload")

        # Apply Study Information
        if metadata.study_information:
            logger.info(f"\n[2/4] Uploading Study Information...")
            num_groups = len(metadata.study_information.groups)
            logger.info(f"  → {num_groups} group(s) to upload")
            processed_ok &= _apply_grouped_metadata(
                conn,
                target_type,
                target_id,
                metadata.study_information.groups,
                f"{namespace}/{SHEET_STUDY}",
            )
        else:
            logger.info(f"\n[2/4] No Study Information to upload")

        # Apply Assay Information
        if metadata.assay_information:
            logger.info(f"\n[3/4] Uploading Assay Information...")
            num_groups = len(metadata.assay_information.groups)
            logger.info(f"  → {num_groups} group(s) to upload")
            processed_ok &= _apply_grouped_metadata(
                conn,
                target_type,
                target_id,
                metadata.assay_information.groups,
                f"{namespace}/{SHEET_ASSAY}",
            )
        else:
            logger.info(f"\n[3/4] No Assay Information to upload")

        # 2. Apply Well-Level Metadata
        logger.info(f"\n[4/4] Uploading Well-Level Metadata (AssayConditions)...")

        if not metadata.assay_conditions:
            logger.info("  → No assay conditions to upload")
        else:
            logger.info(f"  → {len(metadata.assay_conditions)} well condition(s) to upload")
            # Convert to DataFrame for easier processing using to_dict() helper
            conditions_data = [condition.to_dict() for condition in metadata.assay_conditions]

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
        logger.info(f"\n{'=' * 80}")
        logger.info("UPLOAD SUMMARY")
        logger.info(f"{'=' * 80}")

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

        # Log summary details
        if replace:
            logger.info(f"Mode: REPLACE (removed {summary['removed_annotations']} old annotations)")
        else:
            logger.info(f"Mode: APPEND (kept existing annotations)")

        logger.info(f"Target: {target_type} ID {target_id}")
        logger.info(f"Wells processed: {summary['wells_processed']}")
        logger.info(f"Wells succeeded: {summary['wells_succeeded']}")
        logger.info(f"Wells failed: {summary['wells_failed']}")
        logger.info(f"Status: {summary['status'].upper()}")
        logger.info(f"{'=' * 80}\n")

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
    total_groups = len(groups)
    successful_groups = 0

    for group_idx, (group_name, group_data) in enumerate(groups.items(), 1):
        if not isinstance(group_data, dict):
            logger.warning(f"  ⚠ Group '{group_name}' data is not a dictionary, skipping")
            continue

        # Filter out None/NaN values
        kv_pairs = {str(k): str(v) for k, v in group_data.items() if v is not None and pd.notna(v)}

        if not kv_pairs:
            logger.debug(f"  ⊘ Group '{group_name}' is empty after filtering, skipping")
            continue

        # Create namespace for this group
        group_namespace = f"{base_namespace}/{group_name}"

        try:
            logger.info(f"  [{group_idx}/{total_groups}] Uploading group: '{group_name}'")
            logger.info(f"      → {len(kv_pairs)} key-value pair(s)")
            logger.info(f"      → Namespace: {group_namespace}")

            ann_id = create_map_annotation(conn, obj_type, obj_id, kv_pairs, group_namespace)
            if ann_id:
                logger.info(f"      ✓ Created MapAnnotation ID: {ann_id}")
                successful_groups += 1
            else:
                logger.error(f"      ✗ Failed to apply group '{group_name}' metadata")
                success = False
        except Exception as e:
            logger.error(f"      ✗ Error applying group '{group_name}': {e}")
            success = False

    logger.info(f"  → Successfully uploaded {successful_groups}/{total_groups} group(s)")
    return success


def _get_plates_to_process(conn: BlitzGateway, target_type: str, target_id: int) -> list:
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
    logger.info(f"\n{'=' * 80}")
    logger.info(f"REMOVING ANNOTATIONS (namespace: {namespace})")
    logger.info(f"{'=' * 80}")

    total_removed = 0

    # Remove from target object
    logger.info(f"\n[1/3] Processing {target_type} (ID: {target_id})...")
    removed = delete_annotations_from_object(conn, target_type, target_id, namespace)
    total_removed += removed
    logger.info(f"  → Removed {removed} annotation(s) from {target_type}")

    # If Screen, process plates and wells
    if target_type == "Screen":
        screen = conn.getObject("Screen", target_id)
        if screen:
            plates = list(screen.listChildren())
            logger.info(f"\n[2/3] Processing {len(plates)} plate(s) in Screen...")

            for plate_idx, plate in enumerate(plates, 1):
                plate_id = plate.getId()
                plate_name = plate.getName()
                logger.info(f"\n  Plate {plate_idx}/{len(plates)}: '{plate_name}' (ID: {plate_id})")

                removed = delete_annotations_from_object(conn, "Plate", plate_id, namespace)
                total_removed += removed
                logger.info(f"    → Removed {removed} annotation(s) from Plate")

                # Remove from wells
                wells = list(plate.listChildren())
                if wells:
                    logger.info(f"    Processing {len(wells)} well(s)...")
                    well_removed = 0
                    for well in wells:
                        well_id = well.getId()
                        removed = delete_annotations_from_object(conn, "Well", well_id, namespace)
                        well_removed += removed

                    total_removed += well_removed
                    logger.info(
                        f"    → Removed {well_removed} annotation(s) from {len(wells)} well(s)"
                    )

    # If Plate, process wells
    elif target_type == "Plate":
        plate = conn.getObject("Plate", target_id)
        if plate:
            plate_name = plate.getName()
            wells = list(plate.listChildren())
            logger.info(f"\n[2/3] Processing {len(wells)} well(s) in Plate '{plate_name}'...")

            well_removed = 0
            for well in wells:
                well_id = well.getId()
                removed = delete_annotations_from_object(conn, "Well", well_id, namespace)
                well_removed += removed

            total_removed += well_removed
            logger.info(f"  → Removed {well_removed} annotation(s) from {len(wells)} well(s)")

    logger.info(f"\n{'=' * 80}")
    logger.info(f"REMOVAL COMPLETE: {total_removed} total annotations removed")
    logger.info(f"{'=' * 80}\n")

    return total_removed


def download_metadata_from_omero(
    conn: BlitzGateway,
    target_type: Literal["Screen", "Plate"],
    target_id: int,
    namespace: str = DEFAULT_NS_BASE,
) -> MIHCSMEMetadata:
    """
    Download MIHCSME metadata from OMERO and convert to Pydantic model.

    Args:
        conn: OMERO connection
        target_type: "Screen" or "Plate"
        target_id: ID of the target object
        namespace: Namespace for annotations (default: "MIHCSME")

    Returns:
        MIHCSMEMetadata instance populated with data from OMERO

    Example:
        >>> from mihcsme_py import download_metadata_from_omero
        >>> import ezomero
        >>>
        >>> conn = ezomero.connect("omero.example.com", "user", "password")
        >>> metadata = download_metadata_from_omero(conn, "Screen", 123)
        >>> print(metadata.investigation_information.investigation_info.project_id)
    """
    logger.info(f"Downloading metadata from {target_type} {target_id}...")

    # Get the target object
    target_obj = conn.getObject(target_type, target_id)
    if not target_obj:
        raise ValueError(f"{target_type} with ID {target_id} not found")

    # Dictionary to collect all metadata
    metadata_dict = {}

    # Helper function to get annotations from an object
    def get_annotations_as_dict(obj, ns_filter: str) -> Dict[str, Dict[str, Any]]:
        """Get MapAnnotations from an object and organize by namespace.
        
        The namespace structure is expected to be:
        - MIHCSME/InvestigationInformation/DataOwner
        - MIHCSME/InvestigationInformation/InvestigationInfo
        - MIHCSME/StudyInformation/Study
        - MIHCSME/AssayInformation/Assay
        etc.
        
        Where the format is: namespace_base/sheet_name/group_name
        """
        result = {}
        for ann in obj.listAnnotations():
            if hasattr(ann, "getNs") and ann.getNs() and ann.getNs().startswith(ns_filter):
                ns = ann.getNs()
                parts = ns.split("/")
                
                # Extract sheet name (second part) and group name (third part if exists)
                # e.g., "MIHCSME/InvestigationInformation/DataOwner" -> sheet_name="InvestigationInformation", group_name="DataOwner"
                if len(parts) >= 2:
                    sheet_name = parts[1]  # InvestigationInformation, StudyInformation, AssayInformation
                    group_name = parts[2] if len(parts) >= 3 else None  # DataOwner, Study, Assay, etc.
                else:
                    # Fallback for legacy format (just "MIHCSME")
                    sheet_name = parts[-1] if "/" in ns else ns
                    group_name = None

                # Get key-value pairs from MapAnnotation
                if hasattr(ann, "getValue"):
                    kv_pairs = {}
                    for key, value in ann.getValue():
                        kv_pairs[key] = value

                    if kv_pairs:
                        # Initialize sheet if not present
                        if sheet_name not in result:
                            result[sheet_name] = {}

                        # If we have a group name, organize under that group
                        if group_name:
                            if group_name not in result[sheet_name]:
                                result[sheet_name][group_name] = {}
                            result[sheet_name][group_name].update(kv_pairs)
                        else:
                            # No group name, store directly under sheet
                            result[sheet_name].update(kv_pairs)

        return result

    # 1. Get object-level metadata (Investigation, Study, Assay)
    object_annotations = get_annotations_as_dict(target_obj, namespace)

    # The annotations are now already organized by sheet and group
    # e.g., {"InvestigationInformation": {"DataOwner": {...}, "InvestigationInfo": {...}}}
    if SHEET_INVESTIGATION in object_annotations:
        metadata_dict["InvestigationInformation"] = object_annotations[SHEET_INVESTIGATION]

    if SHEET_STUDY in object_annotations:
        metadata_dict["StudyInformation"] = object_annotations[SHEET_STUDY]

    if SHEET_ASSAY in object_annotations:
        metadata_dict["AssayInformation"] = object_annotations[SHEET_ASSAY]

    # 2. Get well-level metadata (AssayConditions)
    assay_conditions = []

    if target_type == "Screen":
        # Iterate through all plates in the screen
        for plate in target_obj.listChildren():
            plate_name = plate.getName()
            for well in plate.listChildren():
                well_data = _get_well_metadata(well, namespace, plate_name)
                if well_data:
                    assay_conditions.append(well_data)

    elif target_type == "Plate":
        plate_name = target_obj.getName()
        for well in target_obj.listChildren():
            well_data = _get_well_metadata(well, namespace, plate_name)
            if well_data:
                assay_conditions.append(well_data)

    if assay_conditions:
        metadata_dict["AssayConditions"] = assay_conditions

    logger.info(f"Downloaded {len(assay_conditions)} well metadata entries")

    # Convert to MIHCSMEMetadata using from_omero_dict
    metadata = MIHCSMEMetadata.from_omero_dict(metadata_dict)

    return metadata


def _organize_into_groups(flat_dict: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Organize flat key-value pairs into groups based on MIHCSME structure.

    The function tries to infer groups from key patterns. For example:
    - Keys starting with common prefixes are grouped together
    - Known group names are detected

    Args:
        flat_dict: Flat dictionary of key-value pairs

    Returns:
        Nested dictionary organized by groups
    """
    # Known group patterns for each sheet type
    known_groups = {
        # Investigation groups
        "First Name": "DataOwner",
        "Middle Name(s)": "DataOwner",
        "Last Name": "DataOwner",
        "User name": "DataOwner",
        "Institute": "DataOwner",
        "E-Mail Address": "DataOwner",
        "ORCID investigator": "DataOwner",
        "Project ID": "InvestigationInformation",
        "Investigation Title": "InvestigationInformation",
        "Investigation internal ID": "InvestigationInformation",
        "Investigation description": "InvestigationInformation",
        # Study groups
        "Study Title": "Study",
        "Study internal ID": "Study",
        "Study Description": "Study",
        "Study Key Words": "Study",
        "Biosample Taxon": "Biosample",
        "Biosample description": "Biosample",
        "Biosample Organism": "Biosample",
        "Number of cell lines used": "Biosample",
        "Library File Name": "Library",
        "Library File Format": "Library",
        "Library Type": "Library",
        "Library Manufacturer": "Library",
        "Library Version": "Library",
        "Library Experimental Conditions": "Library",
        "Quality Control Description": "Library",
        "HCS library protocol": "Protocols",
        "growth protocol": "Protocols",
        "treatment protocol": "Protocols",
        "HCS data analysis protocol": "Protocols",
        "Plate type": "Plate",
        "Plate type Manufacturer": "Plate",
        "Plate type Catalog number": "Plate",
        # Assay groups
        "Assay Title": "Assay",
        "Assay internal ID": "Assay",
        "Assay Description": "Assay",
        "Assay number of biological replicates": "Assay",
        "Number of plates": "Assay",
        "Assay Technology Type": "Assay",
        "Assay Type": "Assay",
        "Assay External URL": "Assay",
        "Assay data URL": "Assay",
        "Imaging protocol": "AssayComponent",
        "Sample preparation protocol": "AssayComponent",
        "Cell lines storage location": "Biosample",
        "Cell lines clone number": "Biosample",
        "Cell lines Passage number": "Biosample",
        # Image data fields
        "Image number of pixelsX": "ImageData",
        "Image number of pixelsY": "ImageData",
        "Image number of  z-stacks": "ImageData",
        "Image number of channels": "ImageData",
        "Image number of timepoints": "ImageData",
        "Image sites per well": "ImageData",
        # Image acquisition fields
        "Microscope id": "ImageAcquisition",
    }

    groups = {}
    for key, value in flat_dict.items():
        # Find the group for this key
        group_name = known_groups.get(key)

        if not group_name:
            # Try to infer from key prefix
            if key.startswith("Channel ") or key == "Channel Transmission id":
                group_name = "Specimen"
            elif "ORCID" in key and "Collaborator" in key:
                group_name = "DataCollaborator"
            else:
                # Default: use "Metadata" as fallback group
                group_name = "Metadata"

        # Add to group
        if group_name not in groups:
            groups[group_name] = {}
        groups[group_name][key] = value

    return groups


def _get_well_metadata(well, namespace: str, plate_name: str) -> Dict[str, Any]:
    """
    Extract metadata from a well.

    Args:
        well: OMERO Well object
        namespace: Namespace to filter annotations
        plate_name: Name of the parent plate

    Returns:
        Dictionary with well metadata including Plate, Well, and conditions
    """
    # Get well position
    row = well.getRow()
    col = well.getColumn()
    well_name = f"{chr(ord('A') + row)}{col + 1:02d}"

    well_data = {
        "Plate": plate_name,
        "Well": well_name,
    }

    # Get annotations from the well
    for ann in well.listAnnotations():
        if hasattr(ann, "getNs") and ann.getNs() and ann.getNs().startswith(namespace):
            # Get key-value pairs from MapAnnotation
            if hasattr(ann, "getValue"):
                for key, value in ann.getValue():
                    well_data[key] = value

    # Only return if we have metadata beyond Plate and Well
    if len(well_data) > 2:
        return well_data
    else:
        return None
