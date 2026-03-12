#!/usr/bin/env python
"""
Create a simple OMERO screen/plate structure with images for testing.

This creates plates with wells and optional synthetic images using ezomero.
Supports multiple runs (PlateAcquisitions) per plate to test multi-run scenarios.

Usage:
    # Create a plate without images
    python create_simple_plate.py --host localhost --user root --plate-name "TestPlate"

    # Create a plate with synthetic images
    python create_simple_plate.py --host localhost --user root --plate-name "TestPlate" --add-images

    # Create a plate with 2 runs (PlateAcquisitions)
    python create_simple_plate.py --host localhost --user root --plate-name "TestPlate" \
        --add-images --num-runs 2

    # Create a plate with named runs
    python create_simple_plate.py --host localhost --user root --plate-name "TestPlate" \
        --add-images --run-names "Run1" "Run2" "Run3"

    # Create a screen with multiple plates, each having 2 runs
    python create_simple_plate.py --host localhost --user root \
        --screen-name "TestScreen" --plate-names "Plate1" "Plate2" --add-images --num-runs 2
"""

import argparse
import getpass
import sys

import numpy as np
import ezomero
from omero.model import PlateI, PlateAcquisitionI, WellI, WellSampleI, ImageI
from omero.rtypes import rstring, rint


def create_plate_layout(rows=8, columns=12):
    """Create well positions for a plate."""
    layout = []
    for row in range(rows):
        for col in range(columns):
            layout.append((row, col))
    return layout


def create_synthetic_image(width=50, height=50, channels=2, z_slices=1, seed=None):
    """
    Create a synthetic image with random noise.

    Returns numpy array in XYZCT order (5D) for ezomero.post_image().
    Shape: (X=width, Y=height, Z=z_slices, C=channels, T=1)
    """
    if seed is not None:
        np.random.seed(seed)

    # Create array in XYZCT order (required by ezomero.post_image)
    # Shape must be: (X, Y, Z, C, T) where all dimensions exist
    image = np.zeros((width, height, z_slices, channels, 1), dtype=np.uint8)

    for c in range(channels):
        for z in range(z_slices):
            # Random noise
            noise = np.random.randint(0, 50, (width, height), dtype=np.uint8)
            # Add some "cells" (bright spots)
            num_cells = np.random.randint(5, 15)
            for _ in range(num_cells):
                cx = np.random.randint(5, width - 5)
                cy = np.random.randint(5, height - 5)
                radius = np.random.randint(2, 5)
                y, x = np.ogrid[:height, :width]
                mask = (x - cx) ** 2 + (y - cy) ** 2 <= radius**2
                noise[mask] = np.random.randint(150, 255)

            image[:, :, z, c, 0] = noise

    # Verify shape before returning
    assert image.shape == (width, height, z_slices, channels, 1), \
        f"Expected shape ({width}, {height}, {z_slices}, {channels}, 1), got {image.shape}"

    return image


def create_plate_acquisitions(conn, plate_id, run_names):
    """
    Create PlateAcquisition (run) objects linked to a plate.

    Args:
        conn: OMERO connection
        plate_id: ID of the plate to link acquisitions to
        run_names: List of run name strings

    Returns:
        List of PlateAcquisition IDs
    """
    acq_ids = []
    update_svc = conn.getUpdateService()
    for name in run_names:
        acq = PlateAcquisitionI()
        acq.setPlate(PlateI(plate_id, False))
        acq.setName(rstring(name))
        acq = update_svc.saveAndReturnObject(acq)
        acq_id = acq.getId().getValue()
        acq_ids.append(acq_id)
        print(f"  Created run '{name}' (PlateAcquisition ID: {acq_id})")
    return acq_ids


def create_simple_plate(
    conn, plate_name, rows=8, columns=12, add_images=False, img_size=50,
    num_runs=1, run_names=None
):
    """
    Create a simple plate with wells, optional images, and optional multiple runs.

    Args:
        conn: OMERO connection
        plate_name: Name for the plate
        rows: Number of rows
        columns: Number of columns
        add_images: Whether to add synthetic images to wells
        img_size: Size of synthetic images (width and height)
        num_runs: Number of runs (PlateAcquisitions) to create (default: 1)
        run_names: Optional list of run names; if None, names are auto-generated
                   (e.g. "Run1", "Run2"). Length determines num_runs when provided.

    Returns:
        Plate ID
    """
    # Resolve run names
    if run_names:
        num_runs = len(run_names)
    else:
        run_names = [f"Run{i + 1}" for i in range(num_runs)]

    print(f"\nCreating plate: {plate_name}")
    print(f"  Layout: {rows} rows × {columns} columns = {rows * columns} wells")
    print(f"  Runs (PlateAcquisitions): {num_runs} ({', '.join(run_names)})")
    if add_images:
        print(f"  Adding {img_size}×{img_size} images per well per run")

    # Create Plate
    plate = PlateI()
    plate.setName(rstring(plate_name))
    plate.setRows(rint(rows))
    plate.setColumns(rint(columns))
    plate.setColumnNamingConvention(rstring("number"))
    plate.setRowNamingConvention(rstring("letter"))

    # Save plate
    plate = conn.getUpdateService().saveAndReturnObject(plate)
    plate_id = plate.getId().getValue()
    print(f"  Plate ID: {plate_id}")

    # Create PlateAcquisition objects (one per run)
    acq_ids = create_plate_acquisitions(conn, plate_id, run_names)

    # Create wells (and optionally images)
    layout = create_plate_layout(rows, columns)
    for idx, (row, col) in enumerate(layout, 1):
        # Generate well name
        row_letter = chr(ord("A") + row)
        well_name = f"{row_letter}{col + 1:02d}"

        # Create well
        well = WellI()
        well.setPlate(PlateI(plate_id, False))  # Use unloaded plate reference
        well.setRow(rint(row))
        well.setColumn(rint(col))

        # For each run, optionally add an image and a WellSample linked to that run
        if add_images:
            for run_idx, acq_id in enumerate(acq_ids):
                # Create synthetic image (XYZCT format); use run_idx in seed for variation
                pixels_data = create_synthetic_image(
                    width=img_size,
                    height=img_size,
                    channels=2,
                    z_slices=1,
                    seed=(plate_id * 10000) + (run_idx * 1000) + idx,
                )

                # Verify shape (must be 5D: X, Y, Z, C, T)
                assert pixels_data.ndim == 5, f"Image must be 5D, got {pixels_data.ndim}D"

                # Upload image using ezomero (creates orphaned image by default)
                image_id = ezomero.post_image(
                    conn=conn,
                    image=pixels_data,
                    image_name=f"{plate_name}_{run_names[run_idx]}_{well_name}",
                    description=f"Synthetic test image - {run_names[run_idx]}",
                    dataset_id=None,  # Explicitly set to None for orphaned images
                )

                if image_id is None:
                    print(f"  WARNING: Failed to create image for {well_name} run '{run_names[run_idx]}'")
                    continue

                # Create WellSample linked to this PlateAcquisition (run)
                ws = WellSampleI()
                ws.setImage(ImageI(image_id, False))  # Use unloaded image reference
                ws.setWell(well)
                ws.setPlateAcquisition(PlateAcquisitionI(acq_id, False))
                well.addWellSample(ws)

        # Save the well (with or without images)
        conn.getUpdateService().saveObject(well)

        # Progress
        if idx % 24 == 0 or idx == len(layout):
            print(f"  Progress: {idx}/{len(layout)} wells")

    print(f"✓ Plate created successfully ({num_runs} run(s), {len(layout)} wells)")
    return plate_id


def create_simple_screen(
    conn, screen_name, plate_names, rows=8, columns=12, add_images=False, img_size=50,
    num_runs=1, run_names=None
):
    """
    Create a simple screen with multiple plates.

    Args:
        conn: OMERO connection
        screen_name: Name for the screen
        plate_names: List of plate names
        rows: Number of rows per plate
        columns: Number of columns per plate
        add_images: Whether to add synthetic images to wells
        img_size: Size of synthetic images
        num_runs: Number of runs (PlateAcquisitions) per plate (default: 1)
        run_names: Optional list of run names shared across all plates

    Returns:
        Screen ID
    """
    print(f"\n{'=' * 60}")
    print(f"Creating screen: {screen_name}")
    print(f"{'=' * 60}")

    # Create Screen using ezomero
    screen_id = ezomero.post_screen(conn, screen_name, description="Test screen")
    print(f"Screen ID: {screen_id}")

    # Create plates
    plate_ids = []
    for plate_name in plate_names:
        plate_id = create_simple_plate(
            conn, plate_name, rows, columns, add_images, img_size,
            num_runs=num_runs, run_names=run_names
        )
        plate_ids.append(plate_id)

    # Link all plates to screen using ezomero
    ezomero.link_plates_to_screen(conn, plate_ids, screen_id)

    resolved_runs = len(run_names) if run_names else num_runs
    print(f"\n{'=' * 60}")
    print(f"✓ Screen created successfully!")
    print(f"  Screen ID: {screen_id}")
    print(f"  Plates: {len(plate_names)}")
    print(f"  Runs per plate: {resolved_runs}")
    print(f"  Total wells: {len(plate_names) * rows * columns}")
    print(f"{'=' * 60}\n")

    return screen_id


def main():
    parser = argparse.ArgumentParser(description="Create simple OMERO screen/plate structure")

    # Connection
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password")
    parser.add_argument("--port", type=int, default=4064)

    # Screen/Plate
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--screen-name")
    group.add_argument("--plate-name")
    parser.add_argument("--plate-names", nargs="+")

    # Layout
    parser.add_argument("--rows", type=int, default=8)
    parser.add_argument("--columns", type=int, default=12)

    # Images
    parser.add_argument("--add-images", action="store_true", help="Add synthetic images to wells")
    parser.add_argument("--img-size", type=int, default=50, help="Size of synthetic images (default: 50)")

    # Runs
    run_group = parser.add_mutually_exclusive_group()
    run_group.add_argument(
        "--num-runs", type=int, default=1,
        help="Number of runs (PlateAcquisitions) per plate (default: 1)"
    )
    run_group.add_argument(
        "--run-names", nargs="+", metavar="NAME",
        help="Explicit run names (e.g. Run1 Run2); overrides --num-runs"
    )

    args = parser.parse_args()

    # Get password
    if not args.password:
        args.password = getpass.getpass(f"Password for {args.user}@{args.host}: ")

    # Connect using ezomero
    print(f"Connecting to {args.host}...")
    conn = ezomero.connect(
        user=args.user,
        password=args.password,
        host=args.host,
        port=args.port,
        secure=True
    )

    if not conn:
        print("Failed to connect!")
        sys.exit(1)

    print(f"✓ Connected as {conn.getUser().getName()}")

    try:
        if args.screen_name:
            if not args.plate_names:
                print("Error: --plate-names required with --screen-name")
                sys.exit(1)

            screen_id = create_simple_screen(
                conn, args.screen_name, args.plate_names,
                args.rows, args.columns, args.add_images, args.img_size,
                num_runs=args.num_runs, run_names=args.run_names,
            )
            print(f"View at: https://{args.host}/webclient/?show=screen-{screen_id}")

        else:
            plate_id = create_simple_plate(
                conn, args.plate_name, args.rows, args.columns,
                args.add_images, args.img_size,
                num_runs=args.num_runs, run_names=args.run_names,
            )
            print(f"View at: https://{args.host}/webclient/?show=plate-{plate_id}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
