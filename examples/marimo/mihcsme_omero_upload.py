import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    from pathlib import Path
    import json
    from pprint import pprint
    import ezomero
    import getpass
    from mihcsme_py import parse_excel_to_model, upload_metadata_to_omero, download_metadata_from_omero
    from mihcsme_py.models import (
        MIHCSMEMetadata,
        AssayCondition,
        InvestigationInformation,
        StudyInformation,
        AssayInformation,
    )
    return (
        ezomero,
        getpass,
        parse_excel_to_model,
        pprint,
        upload_metadata_to_omero,
    )


@app.cell
def _(getpass):
    # OMERO connection parameters (update these!)
    OMERO_HOST = "omero.services.universiteitleiden.nl"  # Change this
    OMERO_USER = "paulmw"  # Change this
    OMERO_PASSWORD = getpass.getpass("password:")

    # Target for upload
    TARGET_TYPE = "Screen"  # or "Plate"
    TARGET_ID = 1402  # Change this to your Screen/Plate ID

    print(f"   Host: {OMERO_HOST}")
    print(f"   User: {OMERO_USER}")
    print(f"   Target: {TARGET_TYPE} ID {TARGET_ID}")
    return OMERO_HOST, OMERO_PASSWORD, OMERO_USER, TARGET_ID


@app.cell
def _(OMERO_HOST, OMERO_PASSWORD, OMERO_USER, ezomero):
    conn = ezomero.connect(
        host=OMERO_HOST,
        user=OMERO_USER,
        password=OMERO_PASSWORD,
        secure=True,
        group="LACDR_CDS_vdWater_RA",
        port=4064,
    )
    return (conn,)


@app.cell
def _(parse_excel_to_model):
    metadata = parse_excel_to_model("examples/LEI-MIHCSME_migration_data_merged.xlsx")
    return (metadata,)


@app.cell
def _(metadata, pprint):
    all_plates = sorted({condition.plate for condition in metadata.assay_conditions})
    pprint(all_plates)
    len(all_plates)
    return


@app.cell
def _(metadata):
    #add .HTD to metadata to match plate names in OMERO
    df =metadata.to_dataframe()
    #df['Plate'] = df['Plate']+".HTD"
    df
    return


@app.cell
def _(metadata):
    metadata.assay_conditions
    return


@app.cell
def _(TARGET_ID, conn, metadata, upload_metadata_to_omero):
    upload_metadata_to_omero(conn, metadata, "Screen", TARGET_ID,replace=False)
    return


if __name__ == "__main__":
    app.run()
