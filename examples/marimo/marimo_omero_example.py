import marimo

__generated_with = "0.18.4"
app = marimo.App()


@app.cell
def _():
    # OMERO connection parameters (update these!)
    OMERO_HOST = "localhost"  # Change this
    OMERO_USER = "root"  # Change this
    OMERO_PASSWORD = "omero"  # Change this (or use getpass)

    # Target for upload
    TARGET_TYPE = "Screen"  # or "Plate"
    TARGET_ID = 13  # Change this to your Screen/Plate ID

    print("⚠️  OMERO Upload Configuration:")
    print(f"   Host: {OMERO_HOST}")
    print(f"   User: {OMERO_USER}")
    print(f"   Target: {TARGET_TYPE} ID {TARGET_ID}")
    print("\n   ⚠️  Update these values before running!")
    return OMERO_HOST, OMERO_PASSWORD, OMERO_USER


@app.cell
def _(OMERO_HOST, OMERO_PASSWORD, OMERO_USER, ezomero):
    # Uncomment to run the upload
    # Connect to OMERO
    print("🔌 Connecting to OMERO...")
    conn = ezomero.connect(
        host=OMERO_HOST,
        user=OMERO_USER,
        password=OMERO_PASSWORD,
        secure=True,
        group="",
        port=4064,
    )
    print("✅ Connected!")
    return


@app.cell
def _(parse_excel_to_model):
    # 1. Parse Excel → Pydantic
    original = parse_excel_to_model("test_MIHCSME.xlsx")
    return (original,)


@app.cell
def _(original, pprint):
    # print all_plates
    all_plates = sorted({condition.plate for condition in original.assay_conditions})
    pprint(all_plates)
    return


@app.cell
def _(original, pd):
    # list all well with treatments in a pandas table
    # Convert to DataFrame using the built-in method
    df = original.to_dataframe()
    print(f"📊 Assay Conditions ({len(df)} wells):\n")
    df.head(10)
    return


@app.cell
def _(pd):
    def plot_plate_layout(metadata, variable="treatment", plate_name=None):
        """
        Display plate layout(s) in DataFrame format showing values in each well.

        Parameters:
        -----------
        metadata : MIHCSMEMetadata
            The parsed MIHCSME metadata object
        variable : str
            The variable to display (e.g., 'treatment', 'cell_line', 'dose')
            Can also be a key from conditions dict
        plate_name : str, optional
            Specific plate to plot. If None, plots all plates

        Returns:
        --------
        dict or DataFrame: Dictionary of DataFrames (one per plate) or single DataFrame
        """
        # Get unique plates
        if plate_name is None:
            plates = sorted({c.plate for c in metadata.assay_conditions})
        else:
            plates = [plate_name]

        # Define plate dimensions (standard 96-well plate)
        rows = ["A", "B", "C", "D", "E", "F", "G", "H"]
        cols = [f"{i:02d}" for i in range(1, 13)]

        result = {}

        for plate in plates:
            # Get conditions for this plate
            plate_conditions = [c for c in metadata.assay_conditions if c.plate == plate]

            # Create a dictionary mapping wells to values
            well_values = {}
            for condition in plate_conditions:
                well = condition.well
                # Get value from conditions dict
                value = condition.conditions.get(variable)
                well_values[well] = value

            # Create DataFrame with row labels and column labels
            data = {}
            for col in cols:
                col_data = []
                for row in rows:
                    well = f"{row}{col}"
                    value = well_values.get(well, "")
                    # Truncate long values for display
                    if isinstance(value, str) and len(value) > 20:
                        value = value[:17] + "..."
                    col_data.append(value)
                data[col] = col_data

            df = pd.DataFrame(data, index=rows)
            result[plate] = df

        # If only one plate, return the DataFrame directly
        if len(result) == 1:
            plate_name = list(result.keys())[0]
            print(f"\n📊 Plate: {plate_name} | Variable: {variable}\n")
            return result[plate_name]

        # If multiple plates, display all
        print(f"\n📊 Variable: {variable} | {len(result)} plates\n")
        return result

    # Example usage:
    # Single plate view:
    # df = plot_plate_layout(original, variable='treatment', plate_name='plate1_1_013')
    # display(df)

    # All plates:
    # plates_dict = plot_plate_layout(original, variable='Gene Symbol')
    # for plate_name, df in plates_dict.items():
    #     print(f"\nPlate: {plate_name}")
    #     display(df)
    return (plot_plate_layout,)


@app.cell
def _(display, original, plot_plate_layout):
    # Display all plates with their layouts
    plates_dict = plot_plate_layout(original, variable="treatment")

    # Show each plate
    for plate_name, plate_df in plates_dict.items():
        print(f"\n{'=' * 80}")
        print(f"Plate: {plate_name}")
        print(f"{'=' * 80}")
        display(plate_df)
        print()
    return


@app.cell
def _():
    from pathlib import Path
    import json
    from pprint import pprint
    import ezomero

    from mihcsme_py import (
        parse_excel_to_model,
        upload_metadata_to_omero,
        download_metadata_from_omero,
    )
    from mihcsme_py.models import (
        MIHCSMEMetadata,
        AssayCondition,
        InvestigationInformation,
        StudyInformation,
        AssayInformation,
    )

    # Optional: For nice table display
    import pandas as pd

    print("✅ Imports successful!")
    return ezomero, parse_excel_to_model, pd, pprint


if __name__ == "__main__":
    app.run()
