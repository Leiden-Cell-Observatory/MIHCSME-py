# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "llm==0.28",
#     "llm-openrouter==0.5",
#     "marimo>=0.19.6",
#     "mihcsme-py[app,omero]",
#     "zeroc-ice",
# ]
#
# [tool.uv.sources]
# zeroc-ice = { url = "https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases/download/20240202/zeroc_ice-3.6.5-cp312-cp312-manylinux_2_28_x86_64.whl" }
# mihcsme-py = { git = "https://github.com/Leiden-Cell-Observatory/MIHCSME-py.git", rev = "main" }
# ///

import marimo

__generated_with = "0.25.0"
app = marimo.App(width="full", app_title="MIHCSME OMERO App")


@app.cell(hide_code=True)
def _(
    OMERO_AVAILABLE,
    export_tab_content,
    get_active_tab,
    load_tab_content,
    metadata_tab_content,
    mo,
    omero_tab_content,
    set_active_tab,
    status_bar,
    wells_tab_content,
):
    # Create the main tabbed interface
    main_tabs = mo.ui.tabs(
        {
            "1. Load Template": load_tab_content,
            "2. Edit Wells": wells_tab_content,
            "3. Edit Metadata": metadata_tab_content,
            "4. Export": export_tab_content,
            "5. OMERO": omero_tab_content
            if OMERO_AVAILABLE
            else mo.callout(
                mo.md(
                    "OMERO support is not installed. Install it with "
                    "`pip install 'mihcsme-py[omero]'` (needs the zeroc-ice wheel). "
                    "All other tabs work offline."
                ),
                kind="info",
            ),
        },
        value=get_active_tab(),
        on_change=set_active_tab,
    )

    # Assemble the main layout
    mo.vstack(
        [
            mo.md("""
        # MIHCSME Metadata Editor + OMERO

        *Create, edit, and sync metadata templates for high-content screening microscopy experiments with OMERO*
        """),
            status_bar,
            mo.md("---"),
            main_tabs,
        ],
        gap=1,
    )
    return


@app.cell
def _(mo):
    # Remember the active tab so edits (which rebuild tab content) don't jump back to tab 1
    get_active_tab, set_active_tab = mo.state("1. Load Template")
    return get_active_tab, set_active_tab


@app.cell
def _(ENABLE_LLM_FEATURES, mo):
    # LLM UI Components - only create if LLM features are enabled
    if ENABLE_LLM_FEATURES:
        llm_model_select = mo.ui.dropdown(
            options=["openrouter/openai/gpt-4o","openrouter/mistralai/mistral-large-2512"],
            value="openrouter/mistralai/mistral-large-2512",
            label="LLM Model:",
        )

        llm_input_text = mo.ui.text_area(
            placeholder="Paste your lab notes, experimental description, or metadata information here...\n\nExample:\nWe performed a high-content screening experiment using HeLa cells treated with DMSO or 10µM compound X. Images were acquired on the Opera Phenix with 40x objective, 4 channels: DAPI (nuclei), GFP (LC3), CY5 (mitochondria), CY3 (actin). 96-well plates from Corning were used.",
            label="Input text (lab notes, descriptions):",
            rows=10,
            full_width=True,
        )

        llm_run_button = mo.ui.run_button(label="Generate Metadata with LLM")
    else:
        llm_model_select = None
        llm_input_text = None
        llm_run_button = None
    return llm_input_text, llm_model_select, llm_run_button


@app.cell
def _():
    # Configuration flag to enable/disable LLM features
    # Set to False to hide all LLM-related UI elements
    ENABLE_LLM_FEATURES = True
    return (ENABLE_LLM_FEATURES,)


@app.cell
def _():
    #import llm
    #for model in llm.get_models():
    #    if (model.supports_schema & model.supports_tools): 
    #        print(model)
    return


@app.cell
def _(ENABLE_LLM_FEATURES):
    import io
    from pathlib import Path

    import marimo as mo
    import pandas as pd

    from mihcsme_py import (
        download_metadata_from_omero,
        parse_excel_to_model,
        upload_metadata_to_omero,
        validate_metadata_against_omero,
        write_metadata_to_excel,
    )
    from mihcsme_py.plate_ops import plate_status

    try:
        import omero  # noqa: F401
        from mihcsme_py.omero_connection import connect as omero_connect

        OMERO_AVAILABLE = True
    except ImportError:
        omero_connect = None
        OMERO_AVAILABLE = False
    from mihcsme_py.forms import assemble_metadata, model_form, render_form
    from mihcsme_py.widgets import PlateViewer

    from importlib.resources import files as _resource_files

    EXAMPLE_FILE = str(_resource_files("mihcsme_py") / "templates" / "MIHCSME_example.xlsx")

    # Only import LLM class if LLM features are enabled
    if ENABLE_LLM_FEATURES:
        from mihcsme_py import MIHCSMEMetadataLLM
    else:
        MIHCSMEMetadataLLM = None

    from mihcsme_py.models import (
        # Assay
        Assay,
        AssayComponent,
        AssayInformation,
        Biosample,
        BiosampleAssay,
        Channel,
        DataCollaborator,
        # Investigation
        DataOwner,
        ImageAcquisition,
        ImageData,
        InvestigationInfo,
        InvestigationInformation,
        Library,
        Plate,
        Protocols,
        Specimen,
        # Study
        Study,
        StudyInformation,
    )

    return (
        AssayInformation,
        EXAMPLE_FILE,
        InvestigationInformation,
        MIHCSMEMetadataLLM,
        OMERO_AVAILABLE,
        Path,
        PlateViewer,
        StudyInformation,
        assemble_metadata,
        download_metadata_from_omero,
        io,
        mo,
        model_form,
        omero_connect,
        parse_excel_to_model,
        pd,
        plate_status,
        render_form,
        upload_metadata_to_omero,
        validate_metadata_against_omero,
        write_metadata_to_excel,
    )


@app.cell(hide_code=True)
def _(ENABLE_LLM_FEATURES, mo):
    # Conditionally include LLM option based on feature flag
    _options = ["File Path", "Upload File"]
    if ENABLE_LLM_FEATURES:
        _options.append("Generate with LLM")

    file_source = mo.ui.radio(
        options=_options,
        value="File Path",
        label="How do you want to load/create the metadata?",
    )
    return (file_source,)


@app.cell
def _(EXAMPLE_FILE, file_source, mo):
    if file_source.value == "File Path":
        path_input = mo.ui.text(
            value=EXAMPLE_FILE,
            label="Excel file path (pre-filled with the bundled example):",
            full_width=True,
        )
        file_upload = None
    elif file_source.value == "Upload File":
        file_upload = mo.ui.file(label="Upload Excel file:", filetypes=[".xlsx"])
        path_input = None
    else:
        # LLM mode - no file input needed here
        file_upload = None
        path_input = None
    return file_upload, path_input


@app.cell
def _(ENABLE_LLM_FEATURES, metadata_from_file, mo):
    # LLM Mode selection - only create if LLM features are enabled
    if not ENABLE_LLM_FEATURES:
        llm_mode = None
        llm_mode_hint = None
    elif metadata_from_file is not None:
        llm_mode = mo.ui.radio(
            options=["Generate from scratch", "Modify existing metadata"],
            value="Modify existing metadata",
            label="Mode:",
        )
        llm_mode_hint = mo.callout(
            mo.md("**Existing metadata detected.** You can modify it with LLM or generate new."),
            kind="info",
        )
    else:
        llm_mode = mo.ui.radio(
            options=["Generate from scratch"],
            value="Generate from scratch",
            label="Mode:",
        )
        llm_mode_hint = mo.callout(
            mo.md(
                "**Tip:** Load an Excel file first (via File Path or Upload), then switch back to LLM to enhance it."
            ),
            kind="info",
        )
    return llm_mode, llm_mode_hint


@app.cell
def _(Path, file_source, file_upload, path_input):
    # Initialize variables for both modes
    file_exists = True  # Default to True for upload mode
    excel_path = None
    load_error = None

    if file_source.value == "File Path":
        # File Path mode: validate the path
        if path_input is not None and path_input.value:
            excel_path = Path(path_input.value)
            file_exists = excel_path.exists()

            if not file_exists:
                load_error = f"File not found: {excel_path}"
    else:
        # Upload File mode: check if file is uploaded
        if file_upload is not None and hasattr(file_upload, "value"):
            if len(file_upload.value) == 0:
                # No file uploaded yet - this is OK, not an error
                file_exists = False  # Flag that we're waiting for upload
                load_error = None
            else:
                # File is uploaded
                file_exists = True
                load_error = None
        else:
            # file_upload not initialized yet
            file_exists = False
            load_error = None
    return excel_path, file_exists, load_error


@app.cell
def _(mo):
    # State to persist metadata loaded from file across mode switches
    # Using mo.state to preserve the value when user switches between modes
    get_persisted_metadata, set_persisted_metadata = mo.state(None)
    return get_persisted_metadata, set_persisted_metadata


@app.cell
def _(mo):
    # State to persist OMERO connection across cell re-runs
    get_omero_conn, set_omero_conn = mo.state(None)
    # State to store OMERO-downloaded metadata
    get_omero_metadata, set_omero_metadata = mo.state(None)
    return (
        get_omero_conn,
        get_omero_metadata,
        set_omero_conn,
        set_omero_metadata,
    )


@app.cell
def _(
    excel_path,
    file_exists,
    file_source,
    file_upload,
    get_persisted_metadata,
    mo,
    parse_excel_to_model,
    set_persisted_metadata,
):
    # Initialize metadata_from_file
    # This preserves metadata when switching to LLM mode
    metadata_from_file = None

    # Check if we're ready to load in File Path or Upload mode
    ready_to_load = False

    if file_source.value == "File Path":
        # File Path mode: ready if file exists
        ready_to_load = file_exists and excel_path is not None
    elif file_source.value == "Upload File":
        # Upload File mode: ready if file is uploaded
        ready_to_load = (
            file_upload is not None and hasattr(file_upload, "value") and len(file_upload.value) > 0
        )

    # Load from file if ready
    if ready_to_load:
        if file_source.value == "File Path":
            try:
                metadata_from_file = parse_excel_to_model(excel_path)
                # Persist the loaded metadata so it's available when switching to LLM mode
                set_persisted_metadata(metadata_from_file)
            except Exception as e:
                # Handle parsing errors gracefully - metadata stays None
                mo.output.append(
                    mo.callout(mo.md(f"**Error parsing Excel file:** {str(e)}"), kind="danger")
                )
        elif file_source.value == "Upload File":
            # Upload File mode
            try:
                # file_upload.contents() returns bytes
                metadata_from_file = parse_excel_to_model(file_upload.contents())
                # Persist the loaded metadata
                set_persisted_metadata(metadata_from_file)
            except Exception as e:
                # Handle parsing errors gracefully - metadata stays None
                mo.output.append(
                    mo.callout(mo.md(f"**Error parsing uploaded file:** {str(e)}"), kind="danger")
                )
    elif file_source.value == "Generate with LLM":
        # In LLM mode, use the persisted metadata from previous file load
        metadata_from_file = get_persisted_metadata()
    return (metadata_from_file,)


@app.cell
def _(
    ENABLE_LLM_FEATURES,
    MIHCSMEMetadataLLM,
    llm_input_text,
    llm_mode,
    llm_model_select,
    llm_run_button,
    metadata_from_file,
    mo,
):
    llm_metadata = None
    llm_error = None
    llm_summary = None  # Summary of what was changed/generated
    llm_was_update = False  # Track if this was an update vs generate

    # Skip LLM processing if features are disabled
    if not ENABLE_LLM_FEATURES:
        pass
    elif llm_run_button is not None and llm_run_button.value and llm_input_text.value:
        import json

        import llm as llm_lib
        import llm_openrouter
        try:
            _model = llm_lib.get_model(llm_model_select.value)

            if llm_mode.value == "Generate from scratch":
                llm_was_update = False
                _prompt = f"""Extract MIHCSME (Minimum Information about High Content Screening Microscopy Experiments) metadata from these lab notes.

    Focus on extracting:
    1. Investigation information: data owner (name, email, ORCID), project ID, investigation title/description
    2. Study information: study title, biosample (organism, taxon, cell lines), library info, protocols, plate type
    3. Assay information: assay title, description, imaging protocol, image data specs (pixels, channels, z-stacks), specimen/channels

    Do NOT include per-well assay conditions - those are handled separately.

    Lab notes:
    {llm_input_text.value}"""
            else:
                # Modify existing mode - use metadata_from_file
                llm_was_update = True
                _current = metadata_from_file.model_dump(
                    exclude={"assay_conditions", "reference_sheets"},
                    exclude_none=True,
                )
                _prompt = f"""Update this existing MIHCSME metadata based on the notes below.
    Keep existing values unless the notes clearly provide better or updated information.
    Fill in empty fields if the notes provide relevant data.

    Current metadata (JSON):
    {json.dumps(_current, indent=2)}

    User notes:
    {llm_input_text.value}"""

            _response = _model.prompt(_prompt, schema=MIHCSMEMetadataLLM)
            _parsed = json.loads(_response.text())

            # Create full metadata object
            if llm_mode.value == "Generate from scratch":
                llm_metadata = MIHCSMEMetadataLLM(**_parsed).to_full_metadata()
                # Generate summary of what was extracted
                _summary_parts = []
                if llm_metadata.investigation_information:
                    _inv = llm_metadata.investigation_information
                    if _inv.investigation_info and _inv.investigation_info.investigation_title:
                        _summary_parts.append(
                            f"Investigation: {_inv.investigation_info.investigation_title}"
                        )
                    if _inv.data_owner and _inv.data_owner.first_name:
                        _summary_parts.append(
                            f"Data owner: {_inv.data_owner.first_name} {_inv.data_owner.last_name or ''}"
                        )
                if llm_metadata.study_information:
                    _study = llm_metadata.study_information
                    if _study.biosample and _study.biosample.biosample_organism:
                        _summary_parts.append(f"Organism: {_study.biosample.biosample_organism}")
                if llm_metadata.assay_information:
                    _assay = llm_metadata.assay_information
                    if _assay.specimen and _assay.specimen.channels:
                        _summary_parts.append(f"Channels: {len(_assay.specimen.channels)}")
                llm_summary = (
                    "; ".join(_summary_parts) if _summary_parts else "Metadata structure created"
                )
            else:
                # Merge with existing (preserving assay_conditions and reference_sheets)
                llm_metadata = metadata_from_file.model_copy(deep=True)
                _llm_result = MIHCSMEMetadataLLM(**_parsed)

                # Track what sections were updated
                _updated_sections = []
                if _llm_result.investigation_information:
                    llm_metadata.investigation_information = _llm_result.investigation_information
                    _updated_sections.append("Investigation")
                if _llm_result.study_information:
                    llm_metadata.study_information = _llm_result.study_information
                    _updated_sections.append("Study")
                if _llm_result.assay_information:
                    llm_metadata.assay_information = _llm_result.assay_information
                    _updated_sections.append("Assay")

                llm_summary = (
                    f"Updated sections: {', '.join(_updated_sections)}"
                    if _updated_sections
                    else "No changes detected"
                )

        except Exception as e:
            llm_error = str(e)
            mo.output.append(mo.callout(mo.md(f"**LLM Error:** {llm_error}"), kind="danger"))
    return llm_error, llm_metadata, llm_summary, llm_was_update


@app.cell
def _(file_source, get_omero_metadata, llm_metadata, metadata_from_file):
    # Combine metadata sources with priority:
    # 1. OMERO-downloaded metadata (highest priority when available)
    # 2. LLM-generated metadata (when in LLM mode)
    # 3. File-loaded metadata (default)
    _omero_meta = get_omero_metadata()
    if _omero_meta is not None:
        metadata = _omero_meta
    elif file_source.value == "Generate with LLM" and llm_metadata is not None:
        metadata = llm_metadata
    else:
        metadata = metadata_from_file
    return (metadata,)


@app.cell(hide_code=True)
def _(
    ENABLE_LLM_FEATURES,
    file_source,
    file_upload,
    llm_error,
    llm_input_text,
    llm_metadata,
    llm_mode,
    llm_mode_hint,
    llm_model_select,
    llm_run_button,
    llm_summary,
    llm_was_update,
    load_error,
    metadata,
    mo,
    path_input,
):
    # Build status message based on state and mode
    if file_source.value == "Generate with LLM":
        # LLM mode status
        if llm_error:
            _load_status = mo.callout(mo.md(f"**LLM Error:** {llm_error}"), kind="danger")
        elif llm_metadata is not None:
            _num_conditions = (
                len(llm_metadata.assay_conditions) if llm_metadata.assay_conditions else 0
            )
            # Distinguish between generated vs updated
            if llm_was_update:
                _action = "Metadata updated with LLM!"
            else:
                _action = "Metadata generated with LLM!"
            # Include summary if available
            _summary_text = f"\n\n*{llm_summary}*" if llm_summary else ""
            _load_status = mo.callout(
                mo.md(f"**{_action}** ({_num_conditions} well conditions){_summary_text}"),
                kind="success",
            )
        else:
            _load_status = mo.callout(
                mo.md(
                    "**Ready.** Enter your lab notes above and click 'Generate Metadata with LLM'."
                ),
                kind="info",
            )
    elif load_error is not None:
        # Error state
        _load_status = mo.callout(mo.md(f"**Error loading template:** {load_error}"), kind="danger")
    elif metadata is not None:
        # Success state
        _num_conditions = len(metadata.assay_conditions) if metadata.assay_conditions else 0
        _load_status = mo.callout(
            mo.md(f"**Template loaded successfully!** ({_num_conditions} well conditions found)"),
            kind="success",
        )
    else:
        # Waiting state - customize message by mode
        if file_source.value == "File Path":
            _load_status = mo.callout(
                mo.md(
                    "**Ready to load.** Enter a file path above and the template will load automatically."
                ),
                kind="info",
            )
        else:
            # Upload mode
            if (
                file_upload is not None
                and hasattr(file_upload, "value")
                and len(file_upload.value) == 0
            ):
                _load_status = mo.callout(
                    mo.md(
                        "**Waiting for file upload.** Click the upload button above to select an Excel file."
                    ),
                    kind="info",
                )
            else:
                _load_status = mo.callout(
                    mo.md("**Ready to upload.** Use the file uploader above."), kind="info"
                )

    # Build the input element based on mode
    if file_source.value == "Generate with LLM":
        _file_input = mo.vstack(
            [
                llm_model_select,
                llm_mode,
                llm_mode_hint,
                mo.md("---"),
                llm_input_text,
                llm_run_button,
            ],
            gap=2,
        )
    elif file_source.value == "File Path":
        _file_input = path_input
    else:
        _file_input = file_upload

    # Fallback if somehow input is None (shouldn't happen but prevents blank screen)
    if _file_input is None:
        _file_input = mo.md("*Please select an input method above*")

    # Build help text based on whether LLM features are enabled
    if ENABLE_LLM_FEATURES:
        _help_text = """
        ### Load Template

        Choose how to load your MIHCSME metadata:
        - **File Path**: Specify a path to an existing Excel file
        - **Upload File**: Upload an Excel file from your computer
        - **Generate with LLM**: Use AI to extract metadata from lab notes
        """
    else:
        _help_text = """
        ### Load Template

        Choose how to load your MIHCSME metadata:
        - **File Path**: Specify a path to an existing Excel file
        - **Upload File**: Upload an Excel file from your computer
        """

    # Assemble the Load tab content
    load_tab_content = mo.vstack(
        [
            mo.md(_help_text),
            file_source,
            _file_input,
            _load_status,
        ],
        gap=2,
    )
    return (load_tab_content,)


@app.cell
def _(metadata, mo, pd):
    # Well dataframe is app state: plate editor and table both write to it
    get_wells, set_wells = mo.state(
        metadata.to_dataframe() if metadata is not None else pd.DataFrame()
    )
    return get_wells, set_wells


@app.cell
def _(PlateViewer, metadata, set_wells):
    # Created once per loaded template; edits flow back via on_change -> set_wells
    plate_viewer = PlateViewer()
    plate_viewer.on_change(set_wells)
    _ = metadata
    return (plate_viewer,)


@app.cell
def _(get_wells, plate_viewer):
    # Push data to the widget; does not depend on the selection (performance rule)
    plate_viewer.set_data(get_wells())
    return


@app.cell
def _(get_wells, mo, set_wells):
    wells_table = mo.ui.data_editor(get_wells(), on_change=set_wells)
    return (wells_table,)


@app.cell(hide_code=True)
def _(form_errors, metadata, mo, plate_viewer, wells_table):
    if metadata is None:
        wells_tab_content = mo.callout(
            mo.md("**Please load a template first** in the Load Template tab."), kind="warn"
        )
    else:
        # Wrapped here (not in its own cell) so selection changes don't re-run any cell
        _plate_viewer_ui = mo.ui.anywidget(plate_viewer)
        _wells_error = form_errors.get("assay_conditions")
        wells_tab_content = mo.vstack(
            [
                mo.md(
                    """
                    ### Plate layout

                    Check your design at a glance. Select wells (drag, row/column headers,
                    legend entries; Shift adds, Esc clears), then set a value in the edit panel.
                    """
                ),
                mo.callout(
                    mo.md(f"**Not saved — fix in the table view:** {_wells_error}"), kind="danger"
                )
                if _wells_error
                else mo.md(""),
                _plate_viewer_ui,
                mo.accordion({"Table view (bulk edit / copy-paste)": wells_table}),
            ],
            gap=2,
        )
    return (wells_tab_content,)


@app.cell
def _(
    AssayInformation,
    InvestigationInformation,
    StudyInformation,
    metadata,
    model_form,
):
    investigation_form = model_form(
        InvestigationInformation, metadata.investigation_information if metadata else None
    )
    study_form = model_form(StudyInformation, metadata.study_information if metadata else None)
    assay_form = model_form(AssayInformation, metadata.assay_information if metadata else None)
    return assay_form, investigation_form, study_form


@app.cell
def _(
    assay_form,
    assemble_metadata,
    get_wells,
    investigation_form,
    metadata,
    study_form,
):
    # Combine edited wells and form sections; errors block export and upload
    form_errors = {}
    metadata_updated = None
    if metadata is not None:
        metadata_updated, form_errors = assemble_metadata(
            metadata,
            get_wells(),
            {
                "investigation_information": investigation_form.value,
                "study_information": study_form.value,
                "assay_information": assay_form.value,
            },
        )
    return form_errors, metadata_updated


@app.cell(hide_code=True)
def _(
    AssayInformation,
    InvestigationInformation,
    StudyInformation,
    assay_form,
    form_errors,
    investigation_form,
    metadata,
    mo,
    render_form,
    study_form,
):
    def _section(key, form, cls):
        _error = form_errors.get(key)
        _parts = [render_form(form, cls)]
        if _error:
            _parts.insert(
                0,
                mo.callout(
                    mo.md(f"**Not saved — fix these fields:**\n\n```\n{_error}\n```"),
                    kind="danger",
                ),
            )
        return mo.vstack(_parts)

    if metadata is None:
        metadata_tab_content = mo.callout(
            mo.md("**Please load a template first** in the Load Template tab."), kind="warn"
        )
    else:
        metadata_tab_content = mo.vstack(
            [
                mo.md(
                    "### Metadata\n\nChanges are applied as you type and used by Export and OMERO upload."
                ),
                mo.ui.tabs(
                    {
                        "Investigation": _section(
                            "investigation_information", investigation_form, InvestigationInformation
                        ),
                        "Study": _section("study_information", study_form, StudyInformation),
                        "Assay": _section("assay_information", assay_form, AssayInformation),
                    }
                ),
            ],
            gap=2,
        )
    return (metadata_tab_content,)


@app.cell
def _(mo):
    export_filename = mo.ui.text(
        value="MIHCSME_export.xlsx", label="Output filename:", full_width=True
    )
    export_button = mo.ui.run_button(label="Export to Excel")
    return export_button, export_filename


@app.cell
def _(
    export_button,
    export_filename,
    form_errors,
    io,
    metadata_updated,
    mo,
    write_metadata_to_excel,
):
    export_result = None
    download_button = None
    if export_button.value and form_errors:
        export_result = mo.callout(
            mo.md(
                "**Not exported:** fix the errors first ("
                + ", ".join(sorted(form_errors))
                + ") in the Edit Wells / Edit Metadata tabs."
            ),
            kind="danger",
        )
    elif export_button.value:
        try:
            _final_metadata = metadata_updated

            # Write to BytesIO buffer for download
            _buffer = io.BytesIO()
            write_metadata_to_excel(_final_metadata, _buffer)
            _buffer.seek(0)

            # Create download button
            download_button = mo.download(
                data=_buffer.getvalue(),
                filename=export_filename.value,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                label="⬇ Download Excel file",
            )

            export_result = mo.callout(
                mo.md("**Export ready!** Click the button below to download."),
                kind="success",
            )
        except Exception as e:
            export_result = mo.callout(mo.md(f"**Error exporting:** {str(e)}"), kind="danger")
    return download_button, export_result


@app.cell(hide_code=True)
def _(
    download_button,
    export_button,
    export_filename,
    export_result,
    metadata,
    metadata_updated,
    mo,
):
    if metadata is None:
        export_tab_content = mo.callout(
            mo.md("**Please load a template first** in the Load Template tab."), kind="warn"
        )
    else:
        # Build summary
        if metadata_updated:
            _summary_df = metadata_updated.to_dataframe()
            _num_plates = len(_summary_df["Plate"].unique()) if len(_summary_df) > 0 else 0
            _num_wells = len(_summary_df)

            _summary = mo.callout(
                mo.md(f"""
                **Summary**
                - Plates: {_num_plates}
                - Wells: {_num_wells}
                - Investigation Info: {"Ready" if metadata_updated.investigation_information else "Not set"}
                """),
                kind="info",
            )
        else:
            _summary = mo.md("*No metadata to display*")

        # Build export controls
        _export_controls = mo.vstack([export_filename, export_button], gap=1)

        # Build download section
        _download_section = (
            mo.vstack([export_result, download_button], gap=1)
            if download_button
            else (export_result if export_result else mo.md(""))
        )

        # Assemble the Export tab content
        export_tab_content = mo.vstack(
            [
                mo.md("""
            ### Review & Export

            Save your completed metadata template to Excel format.
            """),
                _summary,
                mo.md("---"),
                mo.md("**Export Settings**"),
                _export_controls,
                _download_section,
            ],
            gap=2,
        )
    return (export_tab_content,)


@app.cell
def _(mo):
    # OMERO Connection UI Components
    omero_host = mo.ui.text(
        value="omero.example.com",
        label="OMERO Host:",
        full_width=True,
    )
    omero_user = mo.ui.text(
        value="",
        label="Username:",
        full_width=True,
    )
    omero_password = mo.ui.text(
        value="",
        label="Password:",
        kind="password",
        full_width=True,
    )
    omero_port = mo.ui.number(
        value=4064,
        label="Port:",
        start=1,
        stop=65535,
    )
    omero_group = mo.ui.text(
        value="",
        label="Group (optional):",
        full_width=True,
        placeholder="Leave empty for default group",
    )
    omero_secure = mo.ui.checkbox(
        value=True,
        label="Use secure connection (SSL)",
    )
    omero_connect_button = mo.ui.run_button(label="Connect to OMERO")
    omero_disconnect_button = mo.ui.run_button(label="Disconnect")
    return (
        omero_connect_button,
        omero_disconnect_button,
        omero_group,
        omero_host,
        omero_password,
        omero_port,
        omero_secure,
        omero_user,
    )


@app.cell
def _(
    get_omero_conn,
    mo,
    omero_connect,
    omero_connect_button,
    omero_disconnect_button,
    omero_group,
    omero_host,
    omero_password,
    omero_port,
    omero_secure,
    omero_user,
    set_omero_conn,
):
    # OMERO Connection Handler
    omero_conn_error = None
    omero_conn_status = None

    # Handle disconnect
    if omero_disconnect_button.value:
        _conn = get_omero_conn()
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            set_omero_conn(None)
            omero_conn_status = "Disconnected"

    # Handle connect
    if omero_connect_button.value:
        if not omero_host.value or not omero_user.value or not omero_password.value:
            omero_conn_error = "Please fill in host, username, and password"
        else:
            try:
                _new_conn = omero_connect(
                    host=omero_host.value,
                    user=omero_user.value,
                    password=omero_password.value,
                    port=int(omero_port.value),
                    group=omero_group.value if omero_group.value else None,
                    secure=omero_secure.value,
                )
                set_omero_conn(_new_conn)
                omero_conn_status = f"Connected to {omero_host.value} as {omero_user.value}"
            except Exception as e:
                omero_conn_error = str(e)
                set_omero_conn(None)

    # Get current connection status
    _current_conn = get_omero_conn()
    if _current_conn is not None and omero_conn_status is None:
        # Connection exists from previous state
        try:
            # Check if connection is still alive
            if _current_conn.isConnected():
                omero_conn_status = f"Connected to {omero_host.value}"
            else:
                omero_conn_status = "Connection lost"
                set_omero_conn(None)
        except Exception:
            omero_conn_status = "Connection state unknown"

    # Build connection status display
    if omero_conn_error:
        omero_connection_display = mo.callout(
            mo.md(f"**Connection Error:** {omero_conn_error}"), kind="danger"
        )
    elif omero_conn_status and "Connected to" in omero_conn_status:
        omero_connection_display = mo.callout(mo.md(f"**{omero_conn_status}**"), kind="success")
    elif omero_conn_status == "Disconnected":
        omero_connection_display = mo.callout(mo.md("**Disconnected from OMERO**"), kind="info")
    else:
        omero_connection_display = mo.callout(
            mo.md("**Not connected.** Enter credentials and click Connect."), kind="info"
        )
    return (omero_connection_display,)


@app.cell
def _(mo):
    # OMERO Download UI Components
    omero_download_target_type = mo.ui.dropdown(
        options=["Screen", "Plate"],
        value="Screen",
        label="Target Type:",
    )
    omero_download_target_id = mo.ui.number(
        value=1,
        label="Target ID:",
        start=1,
    )
    omero_download_button = mo.ui.run_button(label="Download Metadata from OMERO")
    return (
        omero_download_button,
        omero_download_target_id,
        omero_download_target_type,
    )


@app.cell
def _(
    download_metadata_from_omero,
    get_omero_conn,
    mo,
    omero_download_button,
    omero_download_target_id,
    omero_download_target_type,
    set_omero_metadata,
):
    # OMERO Download Handler
    omero_download_result = None
    omero_download_error = None

    if omero_download_button.value:
        _conn = get_omero_conn()
        if _conn is None:
            omero_download_error = "Not connected to OMERO. Please connect first."
        else:
            try:
                _downloaded_metadata = download_metadata_from_omero(
                    conn=_conn,
                    target_type=omero_download_target_type.value,
                    target_id=int(omero_download_target_id.value),
                )
                set_omero_metadata(_downloaded_metadata)
                _num_conditions = (
                    len(_downloaded_metadata.assay_conditions)
                    if _downloaded_metadata.assay_conditions
                    else 0
                )
                omero_download_result = (
                    f"Downloaded metadata from {omero_download_target_type.value} "
                    f"ID {omero_download_target_id.value}: {_num_conditions} well conditions"
                )
            except Exception as e:
                omero_download_error = str(e)
                set_omero_metadata(None)

    # Build download status display
    if omero_download_error:
        omero_download_display = mo.callout(
            mo.md(f"**Download Error:** {omero_download_error}"), kind="danger"
        )
    elif omero_download_result:
        omero_download_display = mo.callout(
            mo.md(f"**Success!** {omero_download_result}"), kind="success"
        )
    else:
        omero_download_display = mo.md("")
    return (omero_download_display,)


@app.cell
def _(mo):
    # OMERO Upload UI Components
    omero_upload_target_type = mo.ui.dropdown(
        options=["Screen", "Plate"],
        value="Screen",
        label="Target Type:",
    )
    omero_upload_target_id = mo.ui.number(
        value=1,
        label="Target ID:",
        start=1,
    )
    omero_upload_replace = mo.ui.checkbox(
        value=False,
        label="Replace existing annotations (removes old MIHCSME annotations first)",
    )
    omero_upload_strict = mo.ui.checkbox(
        value=True,
        label="Strict validation (block upload on mismatches)",
    )
    omero_upload_button = mo.ui.run_button(label="Upload Metadata to OMERO")
    omero_validate_button = mo.ui.run_button(label="Validate Metadata (dry run)")
    return (
        omero_upload_button,
        omero_upload_replace,
        omero_upload_strict,
        omero_upload_target_id,
        omero_upload_target_type,
        omero_validate_button,
    )


@app.cell
def _(
    form_errors,
    get_omero_conn,
    metadata_updated,
    mo,
    omero_upload_button,
    omero_upload_replace,
    omero_upload_strict,
    omero_upload_target_id,
    omero_upload_target_type,
    upload_metadata_to_omero,
):
    def _build_validation_detail_md(validation):
        """Build markdown string from validation result."""
        lines = []
        if validation.get("errors"):
            lines.append("**Errors (upload blocked):**")
            for err in validation["errors"]:
                lines.append(f"- {err}")
        if validation.get("warnings"):
            lines.append("\n**Warnings:**")
            for warn in validation["warnings"]:
                lines.append(f"- {warn}")
        return "\n".join(lines)

    # OMERO Upload Handler
    omero_upload_result = None
    omero_upload_error = None

    if omero_upload_button.value:
        _conn = get_omero_conn()
        if _conn is None:
            omero_upload_error = "Not connected to OMERO. Please connect first."
        elif metadata_updated is None:
            omero_upload_error = "No metadata to upload. Please load a template first."
        elif form_errors:
            omero_upload_error = (
                "Fix the errors first ("
                + ", ".join(sorted(form_errors))
                + ") in the Edit Wells / Edit Metadata tabs."
            )
        else:
            try:
                # Build final metadata with any form updates
                _final_metadata = metadata_updated

                # Upload to OMERO
                _result = upload_metadata_to_omero(
                    conn=_conn,
                    metadata=_final_metadata,
                    target_type=omero_upload_target_type.value,
                    target_id=int(omero_upload_target_id.value),
                    replace=omero_upload_replace.value,
                    strict=omero_upload_strict.value,
                )

                if _result["status"] == "success":
                    omero_upload_result = (
                        f"Upload successful! "
                        f"Wells: {_result['wells_succeeded']}/{_result['wells_processed']} succeeded"
                    )
                    if omero_upload_replace.value:
                        omero_upload_result += (
                            f", Removed {_result['removed_annotations']} old annotations"
                        )
                elif _result["status"] == "partial_success":
                    omero_upload_result = (
                        f"Partial success. {_result['message']} "
                        f"Wells: {_result['wells_succeeded']}/{_result['wells_processed']}"
                    )
                else:
                    _validation = _result.get("validation")
                    if _validation and not _validation["valid"]:
                        omero_upload_error = (
                            "**Metadata validation failed**\n\n"
                            + _build_validation_detail_md(_validation)
                        )
                    else:
                        omero_upload_error = _result["message"]

            except Exception as e:
                omero_upload_error = str(e)

    # Build upload status display
    if omero_upload_error:
        omero_upload_display = mo.callout(
            mo.md(omero_upload_error), kind="danger"
        )
    elif omero_upload_result:
        if "Partial" in omero_upload_result:
            omero_upload_display = mo.callout(mo.md(f"**{omero_upload_result}**"), kind="warn")
        else:
            omero_upload_display = mo.callout(mo.md(f"**{omero_upload_result}**"), kind="success")
    else:
        omero_upload_display = mo.md("")
    return (omero_upload_display,)


@app.cell
def _(
    get_omero_conn,
    get_wells,
    metadata_updated,
    mo,
    omero_upload_target_id,
    omero_upload_target_type,
    omero_validate_button,
    plate_status,
    validate_metadata_against_omero,
):
    # OMERO Validation (dry run) Handler
    omero_validate_display = mo.md("")

    if omero_validate_button.value:
        _conn = get_omero_conn()
        if _conn is None:
            omero_validate_display = mo.callout(
                mo.md("**Not connected to OMERO.** Please connect first."), kind="danger"
            )
        elif metadata_updated is None:
            omero_validate_display = mo.callout(
                mo.md("**No metadata loaded.** Please load a template first."), kind="danger"
            )
        else:
            try:
                _validation = validate_metadata_against_omero(
                    conn=_conn,
                    metadata=metadata_updated,
                    target_type=omero_upload_target_type.value,
                    target_id=int(omero_upload_target_id.value),
                )

                if _validation["valid"] and not _validation["warnings"]:
                    omero_validate_display = mo.callout(
                        mo.md("**Validation passed.** All plates and wells in metadata match OMERO."),
                        kind="success",
                    )
                elif _validation["valid"] and _validation["warnings"]:
                    _warn_lines = ["**Validation passed with warnings:**\n"]
                    for _w in _validation["warnings"]:
                        _warn_lines.append(f"- {_w}")
                    omero_validate_display = mo.callout(
                        mo.md("\n".join(_warn_lines)), kind="warn"
                    )
                else:
                    _detail_lines = ["**Validation failed:**\n"]
                    if _validation["errors"]:
                        _detail_lines.append("**Errors (would block upload):**")
                        for _e in _validation["errors"]:
                            _detail_lines.append(f"- {_e}")
                    if _validation["warnings"]:
                        _detail_lines.append("\n**Warnings:**")
                        for _w in _validation["warnings"]:
                            _detail_lines.append(f"- {_w}")
                    omero_validate_display = mo.callout(
                        mo.md("\n".join(_detail_lines)), kind="danger"
                    )
                _status_table = mo.ui.table(
                    plate_status(get_wells(), _validation),
                    selection=None,
                    label="Per-plate status",
                )
                omero_validate_display = mo.vstack([omero_validate_display, _status_table])
            except Exception as e:
                omero_validate_display = mo.callout(
                    mo.md(f"**Validation error:** {e}"), kind="danger"
                )
    return (omero_validate_display,)


@app.cell(hide_code=True)
def _(
    get_omero_conn,
    mo,
    omero_connect_button,
    omero_connection_display,
    omero_disconnect_button,
    omero_download_button,
    omero_download_display,
    omero_download_target_id,
    omero_download_target_type,
    omero_group,
    omero_host,
    omero_password,
    omero_port,
    omero_secure,
    omero_upload_button,
    omero_upload_display,
    omero_upload_replace,
    omero_upload_strict,
    omero_upload_target_id,
    omero_upload_target_type,
    omero_user,
    omero_validate_button,
    omero_validate_display,
):
    # Build OMERO Tab Content
    _conn = get_omero_conn()
    _is_connected = _conn is not None

    # Connection section
    _connection_form = mo.vstack(
        [
            mo.md("**Server Settings**"),
            omero_host,
            mo.hstack([omero_port, omero_secure], gap=2),
            mo.md("**Credentials**"),
            omero_user,
            omero_password,
            omero_group,
            mo.hstack([omero_connect_button, omero_disconnect_button], gap=2),
            omero_connection_display,
        ],
        gap=1,
    )

    # Download section
    _download_section = mo.vstack(
        [
            mo.md("""
            **Download metadata from OMERO**

            Load existing MIHCSME metadata from a Screen or Plate in OMERO.
            The downloaded metadata will be available for editing in the other tabs.
            """),
            mo.hstack([omero_download_target_type, omero_download_target_id], gap=2),
            omero_download_button,
            omero_download_display,
        ],
        gap=2,
    )

    # Upload section
    _upload_section = mo.vstack(
        [
            mo.md("""
            **Upload metadata to OMERO**

            Push your current metadata to a Screen or Plate in OMERO.
            This will create MapAnnotations on the target object and its wells.
            Use **Validate** to check plate/well matching before uploading.
            """),
            mo.hstack([omero_upload_target_type, omero_upload_target_id], gap=2),
            omero_upload_replace,
            omero_upload_strict,
            mo.hstack([omero_validate_button, omero_upload_button], gap=2),
            omero_validate_display,
            omero_upload_display,
        ],
        gap=2,
    )

    # Build the OMERO sub-tabs
    _omero_subtabs = mo.ui.tabs(
        {
            "Download": _download_section,
            "Upload": _upload_section,
        }
    )

    # Assemble OMERO tab content
    omero_tab_content = mo.vstack(
        [
            mo.md("""
            ### OMERO Integration

            Connect to an OMERO server to download or upload MIHCSME metadata.
            """),
            mo.md("---"),
            _connection_form,
            mo.md("---"),
            _omero_subtabs
            if _is_connected
            else mo.callout(
                mo.md("**Connect to OMERO** to access download and upload features."),
                kind="info",
            ),
        ],
        gap=2,
    )
    return (omero_tab_content,)


@app.cell(hide_code=True)
def _(get_omero_conn, metadata, mo):
    # Build status bar content
    _conn = get_omero_conn()
    _omero_status = "Connected" if _conn is not None else "Not connected"

    if metadata is not None:
        _df = metadata.to_dataframe()
        _num_plates = len(_df["Plate"].unique()) if len(_df) > 0 else 0
        _num_wells = len(metadata.assay_conditions) if metadata.assay_conditions else 0

        status_bar = mo.hstack(
            [
                mo.stat(value="Loaded", label="Template", bordered=True),
                mo.stat(value=str(_num_plates), label="Plates", bordered=True),
                mo.stat(value=str(_num_wells), label="Wells", bordered=True),
                mo.stat(value=_omero_status, label="OMERO", bordered=True),
            ],
            justify="start",
            gap=2,
        )
    else:
        status_bar = mo.hstack(
            [
                mo.stat(value="Not loaded", label="Template", bordered=True),
                mo.stat(value=_omero_status, label="OMERO", bordered=True),
            ],
            justify="start",
            gap=2,
        )
    return (status_bar,)


if __name__ == "__main__":
    app.run()
