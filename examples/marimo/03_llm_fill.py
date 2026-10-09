# /// script
# requires-python = ">=3.10"
# dependencies = ["marimo>=0.19.6", "mihcsme-py[llm]", "llm-openrouter"]
#
# [tool.uv.sources]
# mihcsme-py = { git = "https://github.com/Leiden-Cell-Observatory/MIHCSME-py.git", rev = "main" }
# ///

import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import llm
    import marimo as mo

    from mihcsme_py import MIHCSMEMetadataLLM

    return MIHCSMEMetadataLLM, llm, mo


@app.cell
def _(mo):
    mo.md("""
    # Fill MIHCSME metadata from lab notes with an LLM

    Paste notes, pick a model (configured via the `llm` CLI, e.g.
    `llm keys set openrouter`) and get structured Investigation / Study /
    Assay information back. Well conditions are not generated.
    """)
    return


@app.cell
def _(llm, mo):
    notes = mo.ui.text_area(
        placeholder="We imaged HeLa cells treated with DMSO or 10 µM compound X on an Opera Phenix, 40x, 4 channels ...",
        full_width=True,
        rows=8,
    )
    model_choice = mo.ui.dropdown(
        options=[m.model_id for m in llm.get_models()], label="Model"
    )
    run = mo.ui.run_button(label="Extract metadata")
    mo.vstack([notes, model_choice, run])
    return model_choice, notes, run


@app.cell
def _(MIHCSMEMetadataLLM, llm, mo, model_choice, notes, run):
    mo.stop(not run.value or not notes.value or not model_choice.value)
    _response = llm.get_model(model_choice.value).prompt(
        f"Extract MIHCSME metadata from these lab notes. Leave unknown fields empty.\n\n{notes.value}",
        schema=MIHCSMEMetadataLLM,
    )
    extracted = MIHCSMEMetadataLLM.model_validate_json(_response.text())
    extracted
    return


if __name__ == "__main__":
    app.run()
