# /// script
# requires-python = ">=3.12"
# dependencies = ["marimo>=0.19.6", "mihcsme-py[omero]", "zeroc-ice"]
#
# [tool.uv.sources]
# zeroc-ice = { url = "https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases/download/20240202/zeroc_ice-3.6.5-cp312-cp312-manylinux_2_28_x86_64.whl" }
# mihcsme-py = { git = "https://github.com/Leiden-Cell-Observatory/MIHCSME-py.git", rev = "main" }
# ///

import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    from importlib.resources import files

    import marimo as mo

    from mihcsme_py import (
        download_metadata_from_omero,
        parse_excel_to_model,
        upload_metadata_to_omero,
        validate_metadata_against_omero,
    )
    from mihcsme_py.omero_connection import connect
    from mihcsme_py.plate_ops import plate_status

    return (
        connect,
        download_metadata_from_omero,
        files,
        mo,
        parse_excel_to_model,
        plate_status,
        upload_metadata_to_omero,
        validate_metadata_against_omero,
    )


@app.cell
def _(mo):
    mo.md("""
    # OMERO round-trip

    Validate a MIHCSME file against an OMERO Screen, upload it, download it
    again and compare. Credentials are typed below and never stored.
    """)
    return


@app.cell
def _(mo):
    login = mo.ui.dictionary(
        {
            "host": mo.ui.text(value="localhost", label="Host"),
            "user": mo.ui.text(label="User"),
            "password": mo.ui.text(kind="password", label="Password"),
            "group": mo.ui.text(label="Group (optional)"),
            "screen_id": mo.ui.number(start=1, step=1, label="Screen ID"),
        }
    ).form(submit_button_label="Connect and validate")
    login
    return (login,)


@app.cell
def _(files, parse_excel_to_model):
    metadata = parse_excel_to_model(
        str(files("mihcsme_py") / "templates" / "MIHCSME_example.xlsx")
    )
    return (metadata,)


@app.cell
def _(connect, login, mo):
    mo.stop(login.value is None, mo.md("Fill in the form to connect."))
    conn = connect(
        host=login.value["host"],
        user=login.value["user"],
        password=login.value["password"],
        group=login.value["group"] or None,
    )
    screen_id = int(login.value["screen_id"])
    return conn, screen_id


@app.cell
def _(
    conn,
    metadata,
    plate_status,
    screen_id,
    validate_metadata_against_omero,
):
    validation = validate_metadata_against_omero(conn, metadata, "Screen", screen_id)
    plate_status(metadata.to_dataframe(), validation)
    return (validation,)


@app.cell
def _(mo, validation):
    upload_button = mo.ui.run_button(label="Upload to OMERO", disabled=not validation["valid"])
    upload_button
    return (upload_button,)


@app.cell
def _(conn, metadata, mo, screen_id, upload_button, upload_metadata_to_omero):
    mo.stop(not upload_button.value)
    upload_result = upload_metadata_to_omero(conn, metadata, "Screen", screen_id)
    upload_result
    return (upload_result,)


@app.cell
def _(conn, download_metadata_from_omero, metadata, screen_id, upload_result):
    # Runs after the upload: download again and compare wells and their values
    _ = upload_result
    downloaded = download_metadata_from_omero(conn, "Screen", screen_id)
    _key = ["Plate", "Well"]
    _original = metadata.to_dataframe().astype(str).sort_values(_key).reset_index(drop=True)
    _roundtrip = (
        downloaded.to_dataframe()
        .astype(str)
        .reindex(columns=_original.columns)
        .sort_values(_key)
        .reset_index(drop=True)
    )
    {
        "uploaded wells": len(_original),
        "downloaded wells": len(_roundtrip),
        "identical": _original.equals(_roundtrip),
    }
    return


if __name__ == "__main__":
    app.run()
