# /// script
# requires-python = ">=3.10"
# dependencies = ["marimo>=0.19.6", "mihcsme-py"]
#
# [tool.uv.sources]
# mihcsme-py = { git = "https://github.com/Leiden-Cell-Observatory/MIHCSME-py.git", rev = "main" }
# ///

import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import io
    from importlib.resources import files

    import marimo as mo

    from mihcsme_py import fill_template, parse_excel_to_model, write_metadata_to_excel

    return (
        files,
        fill_template,
        io,
        mo,
        parse_excel_to_model,
        write_metadata_to_excel,
    )


@app.cell
def _(mo):
    mo.md("""
    # Parse and explore a MIHCSME file

    Load a MIHCSME Excel file into a validated Pydantic model, look at the
    well conditions as a table and write it back to Excel.
    """)
    return


@app.cell
def _(files, parse_excel_to_model):
    example_path = files("mihcsme_py") / "templates" / "MIHCSME_example.xlsx"
    metadata = parse_excel_to_model(str(example_path))
    metadata.investigation_information
    return (metadata,)


@app.cell
def _(metadata):
    metadata.study_information
    return


@app.cell
def _(metadata):
    wells = metadata.to_dataframe()
    wells
    return (wells,)


@app.cell
def _(wells):
    wells.groupby("Plate").size().rename("wells per plate")
    return


@app.cell
def _(io, metadata, mo, write_metadata_to_excel):
    _buffer = io.BytesIO()
    write_metadata_to_excel(metadata, _buffer)
    mo.download(_buffer.getvalue(), filename="metadata_export.xlsx", label="Download as Excel")
    return


@app.cell
def _(fill_template, io, metadata, mo):
    _buffer = io.BytesIO()
    fill_template(metadata, _buffer)
    mo.download(_buffer.getvalue(), filename="LEI-MIHCSME_filled.xlsx", label="Download filled LEI template")
    return


if __name__ == "__main__":
    app.run()
