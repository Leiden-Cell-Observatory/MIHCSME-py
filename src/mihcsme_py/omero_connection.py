"""OMERO connection and utility functions using omero-py directly."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from omero.gateway import BlitzGateway

logger = logging.getLogger(__name__)


def _check_omero_available() -> None:
    """Check if omero-py is installed, raise ImportError if not."""
    try:
        import omero  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "omero-py is required for OMERO functionality. "
            "Install zeroc-ice first, then install with: pip install mihcsme-py[omero]"
        ) from e


def connect(
    host: str,
    user: str,
    password: str,
    port: int = 4064,
    group: Optional[str] = None,
    secure: bool = True,
) -> BlitzGateway:
    """
    Create a connection to OMERO server.

    Args:
        host: OMERO server hostname
        user: OMERO username
        password: OMERO password
        port: OMERO server port (default: 4064)
        group: OMERO group name (optional)
        secure: Use secure connection (default: True)

    Returns:
        BlitzGateway connection object

    Raises:
        ConnectionError: If connection fails
    """
    _check_omero_available()
    from omero.gateway import BlitzGateway

    logger.info(f"Connecting to OMERO: {user}@{host}:{port}")

    conn = BlitzGateway(user, password, host=host, port=port, secure=secure)

    if not conn.connect():
        logger.error("Failed to connect to OMERO")
        raise ConnectionError(f"Failed to connect to OMERO server at {host}:{port}")

    logger.info(f"Connected to OMERO as {user}")

    # Set group if specified
    if group:
        conn.setGroupForSession(group)
        logger.info(f"Set group context to: {group}")

    return conn


def create_map_annotation(
    conn: BlitzGateway,
    object_type: str,
    object_id: int,
    key_value_pairs: dict,
    namespace: str,
) -> Optional[int]:
    """
    Create and link a MapAnnotation to an OMERO object.

    Args:
        conn: Active OMERO connection
        object_type: Type of object ("Screen", "Plate", "Well", etc.)
        object_id: ID of the object
        key_value_pairs: Dictionary of metadata key-value pairs
        namespace: Namespace for the annotation

    Returns:
        Annotation ID if successful, None otherwise

    Raises:
        ValueError: If object not found or parameters invalid
    """
    if not key_value_pairs:
        logger.debug(f"No key-value pairs to annotate for {object_type} {object_id}")
        return None

    _check_omero_available()
    import omero.gateway

    try:
        # Get the target object
        obj = conn.getObject(object_type, object_id)
        if obj is None:
            raise ValueError(f"{object_type} with ID {object_id} not found")

        # Create MapAnnotation
        map_ann = omero.gateway.MapAnnotationWrapper(conn)
        map_ann.setNs(namespace)

        # Convert dict to list of (key, value) tuples, all as strings
        key_value_list = [[str(k), str(v)] for k, v in key_value_pairs.items()]
        map_ann.setValue(key_value_list)

        # Save the annotation
        map_ann.save()

        # Link annotation to the object
        obj.linkAnnotation(map_ann)

        annotation_id = map_ann.getId()
        logger.debug(
            f"Created MapAnnotation {annotation_id} for {object_type} {object_id} "
            f"with {len(key_value_pairs)} key-value pairs"
        )

        return annotation_id

    except Exception as e:
        logger.error(f"Failed to create MapAnnotation for {object_type} {object_id}: {e}")
        raise


def get_wells_from_plate(conn: BlitzGateway, plate_id: int) -> list:
    """
    Get all wells from a plate.

    Args:
        conn: Active OMERO connection
        plate_id: Plate ID

    Returns:
        List of WellWrapper objects
    """
    plate = conn.getObject("Plate", plate_id)
    if not plate:
        logger.warning(f"Plate {plate_id} not found")
        return []

    wells = list(plate.listChildren())
    logger.debug(f"Found {len(wells)} wells in Plate {plate_id}")
    return wells


def delete_annotations_from_object(
    conn: BlitzGateway,
    object_type: str,
    object_id: int,
    namespace: Optional[str] = None,
) -> int:
    """
    Delete annotations from an OMERO object.

    Args:
        conn: Active OMERO connection
        object_type: Type of object ("Screen", "Plate", "Well", etc.)
        object_id: ID of the object
        namespace: If specified, only delete annotations with this namespace prefix

    Returns:
        Number of annotations deleted
    """
    obj = conn.getObject(object_type, object_id)
    if not obj:
        logger.warning(f"{object_type} {object_id} not found")
        return 0

    # Get object name for better logging
    obj_name = getattr(obj, "getName", lambda: None)() or f"ID:{object_id}"

    annotations_to_delete = []
    preserved_annotations = []

    for ann in obj.listAnnotations():
        ann_id = ann.getId()
        ann_type = type(ann).__name__
        ann_ns = None

        # Get namespace if available
        if hasattr(ann, "getNs"):
            ann_ns = ann.getNs()

        # Filter by namespace if specified
        if namespace:
            # Skip annotations without getNs attribute (e.g., some annotation types)
            if not hasattr(ann, "getNs"):
                preserved_annotations.append(
                    f"  ✓ Preserved {ann_type} ID:{ann_id} (no getNs method)"
                )
                continue

            # Skip annotations with no namespace (e.g., FileAnnotations)
            if not ann_ns:
                preserved_annotations.append(
                    f"  ✓ Preserved {ann_type} ID:{ann_id} (no namespace)"
                )
                continue

            # Skip annotations whose namespace doesn't match the filter
            if not ann_ns.startswith(namespace):
                preserved_annotations.append(
                    f"  ✓ Preserved {ann_type} ID:{ann_id} (namespace: {ann_ns})"
                )
                continue

        # This annotation will be deleted
        annotations_to_delete.append(ann_id)
        logger.info(f"  ✗ Deleting {ann_type} ID:{ann_id} (namespace: {ann_ns})")

    # Log preserved annotations at debug level
    if preserved_annotations:
        logger.debug(f"{object_type} '{obj_name}' - Preserved annotations:")
        for msg in preserved_annotations:
            logger.debug(msg)

    if annotations_to_delete:
        logger.info(
            f"{object_type} '{obj_name}' - Deleting {len(annotations_to_delete)} "
            f"annotation(s) matching namespace '{namespace}'"
        )
        conn.deleteObjects("Annotation", annotations_to_delete, wait=True)
    else:
        logger.debug(f"{object_type} '{obj_name}' - No annotations to delete")

    return len(annotations_to_delete)
