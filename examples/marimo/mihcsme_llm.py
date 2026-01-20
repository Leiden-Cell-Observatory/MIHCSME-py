import marimo

__generated_with = "0.19.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import llm
    import mihcsme_py

    from pprint import pprint

    from mihcsme_py import (
        parse_excel_to_model,
        write_metadata_to_excel,
    )
    from mihcsme_py.models import (
        DataOwner,
        InvestigationInfo,
        InvestigationInformation,
        MIHCSMEMetadata
    )
    return (
        MIHCSMEMetadata,
        llm,
        parse_excel_to_model,
        pprint,
        write_metadata_to_excel,
    )


@app.cell
def _(parse_excel_to_model):
    from pathlib import Path

    # Parse Excel file to Pydantic model
    excel_path = Path("MIHCSME Template_example.xlsx")
    metadata = parse_excel_to_model(excel_path)
    return (metadata,)


@app.cell
def _(metadata):
    metadata
    return


@app.cell
def _(llm, metadata):
    model = llm.get_model("gpt-4o")

    resp = model.prompt(f"turn this in a somebody's lab journal notes, ignore the  Assay condition tab {metadata}")
    return model, resp


@app.cell
def _(pprint, resp):
    pprint(resp.text())
    return


@app.cell
def _(MIHCSMEMetadata, model, resp):
    resp2 = model.prompt(f"Ignore the assay conditions try to fill in the other field if you find the needed information {resp.text()}",schema=MIHCSMEMetadata)
    return (resp2,)


@app.cell
def _(resp2):
    resp2.json()
    return


@app.cell
def _(MIHCSMEMetadata, resp2):
    # Ensure you're accessing the text attribute correctly
    response_text = resp2.text()  # Make sure this is a string

    # Check the type of response_text
    assert isinstance(response_text, str), "response_text should be a string"

    # Convert response text to a dictionary
    import json
    parsed_data = json.loads(response_text)

    # Create an instance of the Pydantic model
    metadata_instance = MIHCSMEMetadata(**parsed_data)

    # Display the instance
    metadata_instance
    return (metadata_instance,)


@app.cell
def _(metadata_instance, write_metadata_to_excel):
    output_path = "LLM_metadata.xlsx"
    write_metadata_to_excel(metadata_instance, output_path)

    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
