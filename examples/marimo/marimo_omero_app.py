import marimo

__generated_with = "0.19.4"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(
    export_tab_content,
    load_tab_content,
    metadata_tab_content,
    mo,
    omero_tab_content,
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
            "5. OMERO": omero_tab_content,
        }
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
        write_metadata_to_excel,
    )
    from mihcsme_py.omero_connection import connect as omero_connect

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
        Assay,
        AssayComponent,
        AssayInformation,
        Biosample,
        BiosampleAssay,
        Channel,
        DataCollaborator,
        DataOwner,
        ImageAcquisition,
        ImageData,
        InvestigationInfo,
        InvestigationInformation,
        Library,
        MIHCSMEMetadataLLM,
        Path,
        Plate,
        Protocols,
        Specimen,
        Study,
        StudyInformation,
        download_metadata_from_omero,
        io,
        mo,
        omero_connect,
        parse_excel_to_model,
        pd,
        upload_metadata_to_omero,
        write_metadata_to_excel,
    )


@app.cell(hide_code=True)
def _(pd):
    def visualize_plate(df, column_to_display, plate_name=None, plate_format="96"):
        """
        Visualize a dataframe as a well plate layout.

        Args:
            df: DataFrame with 'Plate', 'Well' columns and data columns
            column_to_display: Name of the column to show in each well
            plate_name: Optional plate name to filter by (if None, uses first plate)
            plate_format: "96" for 96-well (8x12) or "384" for 384-well (16x24)

        Returns:
            HTML string with plate visualization
        """
        # Define plate dimensions based on format
        if plate_format == "96":
            max_rows = 8  # A-H
            max_cols = 12  # 1-12
        else:  # 384-well
            max_rows = 16  # A-P
            max_cols = 24  # 1-24

        # Create full row and column ranges
        row_letters = [chr(65 + i) for i in range(max_rows)]  # A, B, C, ...
        col_numbers = list(range(1, max_cols + 1))

        # Filter by plate if specified
        if plate_name:
            plate_df = df[df["Plate"] == plate_name].copy()
        else:
            # Use first plate if not specified
            plate_name = df["Plate"].iloc[0] if len(df) > 0 else "Unknown"
            plate_df = df[df["Plate"] == plate_name].copy()

        # Parse well positions (e.g., "A01" -> row="A", col=1)
        def parse_well(well_str):
            row = well_str[0]  # Letter (A-P)
            col = int(well_str[1:])  # Number (1-48)
            return row, col

        # Create lookup dictionary for data
        well_data_dict = {}
        if len(plate_df) > 0:
            plate_df["row"] = plate_df["Well"].apply(lambda w: parse_well(w)[0])
            plate_df["col"] = plate_df["Well"].apply(lambda w: parse_well(w)[1])

            for _, row_data in plate_df.iterrows():
                key = (row_data["row"], row_data["col"])
                well_data_dict[key] = row_data[column_to_display]

        # Create HTML table
        html = f"<h3>Plate: {plate_name} - {column_to_display} ({plate_format}-well)</h3>"
        html += (
            "<table style='border-collapse: collapse; font-family: monospace; font-size: 10px;'>"
        )

        # Header row (column numbers)
        html += "<tr><th style='border: 1px solid #ddd; padding: 4px; background: #f0f0f0; font-size: 9px;'></th>"
        for col in col_numbers:
            html += f"<th style='border: 1px solid #ddd; padding: 4px; background: #f0f0f0; font-size: 9px;'>{col}</th>"
        html += "</tr>"

        # Data rows - always show full grid
        for row_letter in row_letters:
            html += f"<tr><th style='border: 1px solid #ddd; padding: 4px; background: #f0f0f0; font-size: 9px;'>{row_letter}</th>"
            for col_num in col_numbers:
                # Look up data for this well
                key = (row_letter, col_num)
                if key in well_data_dict:
                    value = well_data_dict[key]
                    # Format value
                    if pd.isna(value):
                        display_value = "-"
                        bg_color = "#f9f9f9"
                    else:
                        display_value = str(value)
                        # Truncate long values
                        if len(display_value) > 10:
                            display_value = display_value[:8] + ".."
                        bg_color = "#e3f2fd"  # Light blue for data
                else:
                    # Empty well (no data)
                    display_value = ""
                    bg_color = "#ffffff"

                html += f"<td style='border: 1px solid #ddd; padding: 4px; background: {bg_color}; text-align: center; min-width: 40px; font-size: 9px;'>{display_value}</td>"
            html += "</tr>"

        html += "</table>"
        return html
    return (visualize_plate,)


@app.function(hide_code=True)
def create_pydantic_form(mo, model_class, instance=None):
    form_fields = {}
    for field_name, field_info in model_class.model_fields.items():
        alias = field_info.alias or field_name
        description = field_info.description or ""
        current_value = getattr(instance, field_name, None) if instance else None

        if current_value is None:
            current_value = ""

        form_fields[field_name] = mo.ui.text(
            value=str(current_value),
            label=alias,
            placeholder=description[:50] if description else "",
        )
    return form_fields


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
def _(file_source, mo):
    if file_source.value == "File Path":
        path_input = mo.ui.text(
            value="MIHCSME Template_example.xlsx", label="Excel file path:", full_width=True
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
def _(metadata):
    # Don't stop - just return None for df when metadata is None
    # This allows downstream cells to check and handle the None case
    df = None
    if metadata is not None:
        df = metadata.to_dataframe()
    return (df,)


@app.cell(hide_code=True)
def _(df, mo):
    # Create default controls even when df is None
    # This prevents "ancestor stopped" errors in downstream cells

    if df is not None:
        # Get available columns (excluding Plate and Well)
        data_columns = [col for col in df.columns if col not in ["Plate", "Well"]]

        # Get unique plates
        plates = df["Plate"].unique().tolist() if len(df) > 0 else []
    else:
        # No data yet - create empty controls
        data_columns = []
        plates = []

    # Create interactive controls (they work even with empty options)
    column_select = mo.ui.dropdown(
        options=data_columns,
        value=data_columns[0] if data_columns else None,
        label="Column to display:",
    )

    plate_select = mo.ui.dropdown(
        options=plates, value=plates[0] if plates else None, label="Plate:"
    )

    format_select = mo.ui.dropdown(options=["96", "384"], value="96", label="Plate format:")
    return column_select, format_select, plate_select


@app.cell
def _(df, mo, pd):
    # Create editor even when df is None - use empty dataframe as placeholder
    if df is not None:
        editor = mo.ui.data_editor(df)
    else:
        # Create empty editor as placeholder
        editor = mo.ui.data_editor(pd.DataFrame())
    return (editor,)


@app.cell
def _(editor, metadata, pd):
    # Handle case when metadata is None
    if metadata is not None:
        metadata_updated = metadata.update_conditions_from_dataframe(editor.value)
        df_updated = metadata_updated.to_dataframe()
    else:
        # No metadata yet - use empty values
        metadata_updated = None
        df_updated = pd.DataFrame()
    return df_updated, metadata_updated


@app.cell(hide_code=True)
def _(
    column_select,
    df_updated,
    editor,
    format_select,
    metadata,
    mo,
    plate_select,
    visualize_plate,
):
    if metadata is None:
        wells_tab_content = mo.callout(
            mo.md("**Please load a template first** in the Load Template tab."), kind="warn"
        )
    else:
        # Build controls row
        _controls = mo.hstack([plate_select, column_select, format_select], gap=2)

        # Build plate visualization
        if column_select.value and plate_select.value:
            _plate_html = visualize_plate(
                df_updated, column_select.value, plate_select.value, format_select.value
            )
            _plate_viz = mo.Html(_plate_html)
        else:
            _plate_viz = mo.md("Select a column and plate to visualize")

        # Assemble the Wells tab content
        wells_tab_content = mo.vstack(
            [
                mo.md("""
            ### Edit Plates & Wells

            View and modify well-level metadata across your plates.

            **Instructions:**
            1. Use the dropdowns to select which plate and column to visualize
            2. Edit data directly in the table below
            3. The plate visualization updates automatically
            """),
                mo.md("---"),
                mo.md("**Visualization Controls**"),
                _controls,
                _plate_viz,
                mo.md("---"),
                mo.md("**Data Editor** - Edit well metadata directly:"),
                editor,
            ],
            gap=2,
        )
    return (wells_tab_content,)


@app.cell(hide_code=True)
def _(DataOwner, InvestigationInfo, metadata, mo):
    if metadata is None:
        inv_data_owner_fields = None
        inv_investigation_info_fields = None
        inv_collaborators_array = None
        inv_investigation_forms = None
    else:
        # Data Owner form
        _current_data_owner = (
            metadata.investigation_information.data_owner
            if metadata.investigation_information
            else None
        )
        inv_data_owner_fields = create_pydantic_form(mo, DataOwner, _current_data_owner)

        _inv_data_owner_form = mo.vstack(
            [
                mo.md("**Data Owner Information**"),
                inv_data_owner_fields["first_name"],
                inv_data_owner_fields["middle_names"],
                inv_data_owner_fields["last_name"],
                inv_data_owner_fields["user_name"],
                inv_data_owner_fields["institute"],
                inv_data_owner_fields["email"],
                inv_data_owner_fields["orcid"],
            ]
        )

        # Investigation Info form
        _current_investigation_info = (
            metadata.investigation_information.investigation_info
            if metadata.investigation_information
            else None
        )
        inv_investigation_info_fields = create_pydantic_form(
            mo, InvestigationInfo, _current_investigation_info
        )

        _inv_investigation_info_form = mo.vstack(
            [
                mo.md("**Investigation Information**"),
                inv_investigation_info_fields["project_id"],
                inv_investigation_info_fields["investigation_title"],
                inv_investigation_info_fields["investigation_internal_id"],
                inv_investigation_info_fields["investigation_description"],
            ]
        )

        # Data Collaborators array
        _current_collaborators = (
            metadata.investigation_information.data_collaborators
            if metadata.investigation_information
            else []
        )
        # Create initial array elements from existing collaborators
        _initial_collab_elements = [
            mo.ui.text(
                label=f"ORCID Collaborator",
                placeholder="https://orcid.org/0000-0000-0000-0000",
                value=collab.orcid or "",
            )
            for collab in _current_collaborators
        ] or [
            mo.ui.text(
                label="ORCID Collaborator",
                placeholder="https://orcid.org/0000-0000-0000-0000",
            )
        ]

        inv_collaborators_array = mo.ui.array(
            _initial_collab_elements, label="Data Collaborators (add/remove as needed)"
        )

        _inv_collaborators_form = mo.vstack(
            [mo.md("**Data Collaborators**"), inv_collaborators_array]
        )

        # Combine into tabs
        inv_investigation_forms = mo.ui.tabs(
            {
                "Data Owner": _inv_data_owner_form,
                "Investigation Info": _inv_investigation_info_form,
                "Collaborators": _inv_collaborators_form,
            }
        ).form(label="Update Investigation Information", bordered=True)
    return (
        inv_collaborators_array,
        inv_data_owner_fields,
        inv_investigation_forms,
        inv_investigation_info_fields,
    )


@app.cell
def _(
    DataCollaborator,
    DataOwner,
    InvestigationInfo,
    inv_collaborators_array,
    inv_data_owner_fields,
    inv_investigation_forms,
    inv_investigation_info_fields,
):
    inv_updated_data_owner = None
    inv_updated_investigation_info = None
    inv_updated_collaborators = []

    if inv_investigation_forms is not None and inv_investigation_forms.value:
        inv_updated_data_owner = DataOwner(
            first_name=inv_data_owner_fields["first_name"].value or None,
            middle_names=inv_data_owner_fields["middle_names"].value or None,
            last_name=inv_data_owner_fields["last_name"].value or None,
            user_name=inv_data_owner_fields["user_name"].value or None,
            institute=inv_data_owner_fields["institute"].value or None,
            email=inv_data_owner_fields["email"].value or None,
            orcid=inv_data_owner_fields["orcid"].value or None,
        )

        inv_updated_investigation_info = InvestigationInfo(
            project_id=inv_investigation_info_fields["project_id"].value or None,
            investigation_title=inv_investigation_info_fields["investigation_title"].value or None,
            investigation_internal_id=inv_investigation_info_fields[
                "investigation_internal_id"
            ].value
            or None,
            investigation_description=inv_investigation_info_fields[
                "investigation_description"
            ].value
            or None,
        )

        # Process collaborators array
        inv_updated_collaborators = [
            DataCollaborator(orcid=item.value or None)
            for item in inv_collaborators_array.value
            if item.value and item.value.strip()
        ]
    return (
        inv_updated_collaborators,
        inv_updated_data_owner,
        inv_updated_investigation_info,
    )


@app.cell
def _(Biosample, Library, Plate, Protocols, Study, metadata, mo):
    """Create Study Information forms."""
    if metadata is None:
        study_fields = None
        biosample_fields = None
        library_fields = None
        protocols_fields = None
        plate_fields = None
        study_forms = None
    else:
        # Study form
        _current_study = metadata.study_information.study if metadata.study_information else None
        study_fields = create_pydantic_form(mo, Study, _current_study)
        _study_form = mo.vstack(
            [
                mo.md("**Study Information**"),
                study_fields["study_title"],
                study_fields["study_internal_id"],
                study_fields["study_description"],
                study_fields["study_key_words"],
            ]
        )

        # Biosample form
        _current_biosample = (
            metadata.study_information.biosample if metadata.study_information else None
        )
        biosample_fields = create_pydantic_form(mo, Biosample, _current_biosample)
        _biosample_form = mo.vstack(
            [
                mo.md("**Biosample Information**"),
                biosample_fields["biosample_taxon"],
                biosample_fields["biosample_description"],
                biosample_fields["biosample_organism"],
                biosample_fields["number_of_cell_lines_used"],
            ]
        )

        # Library form
        _current_library = (
            metadata.study_information.library if metadata.study_information else None
        )
        library_fields = create_pydantic_form(mo, Library, _current_library)
        _library_form = mo.vstack(
            [
                mo.md("**Library Information**"),
                library_fields["library_file_name"],
                library_fields["library_file_format"],
                library_fields["library_type"],
                library_fields["library_manufacturer"],
                library_fields["library_version"],
                library_fields["library_experimental_conditions"],
                library_fields["quality_control_description"],
            ]
        )

        # Protocols form
        _current_protocols = (
            metadata.study_information.protocols if metadata.study_information else None
        )
        protocols_fields = create_pydantic_form(mo, Protocols, _current_protocols)
        _protocols_form = mo.vstack(
            [
                mo.md("**Protocols**"),
                protocols_fields["hcs_library_protocol"],
                protocols_fields["growth_protocol"],
                protocols_fields["treatment_protocol"],
                protocols_fields["hcs_data_analysis_protocol"],
            ]
        )

        # Plate form
        _current_plate = metadata.study_information.plate if metadata.study_information else None
        plate_fields = create_pydantic_form(mo, Plate, _current_plate)
        _plate_form = mo.vstack(
            [
                mo.md("**Plate Information**"),
                plate_fields["plate_type"],
                plate_fields["plate_type_manufacturer"],
                plate_fields["plate_type_catalog_number"],
            ]
        )

        # Combine into tabs
        study_forms = mo.ui.tabs(
            {
                "Study": _study_form,
                "Biosample": _biosample_form,
                "Library": _library_form,
                "Protocols": _protocols_form,
                "Plate": _plate_form,
            }
        ).form(label="Update Study Information", bordered=True)
    return (
        biosample_fields,
        library_fields,
        plate_fields,
        protocols_fields,
        study_fields,
        study_forms,
    )


@app.cell
def _(
    Biosample,
    Library,
    Plate,
    Protocols,
    Study,
    biosample_fields,
    library_fields,
    plate_fields,
    protocols_fields,
    study_fields,
    study_forms,
):
    """Process Study Information form submission."""
    study_updated_study = None
    study_updated_biosample = None
    study_updated_library = None
    study_updated_protocols = None
    study_updated_plate = None

    if study_forms is not None and study_forms.value:
        study_updated_study = Study(
            study_title=study_fields["study_title"].value or None,
            study_internal_id=study_fields["study_internal_id"].value or None,
            study_description=study_fields["study_description"].value or None,
            study_key_words=study_fields["study_key_words"].value or None,
        )

        study_updated_biosample = Biosample(
            biosample_taxon=biosample_fields["biosample_taxon"].value or None,
            biosample_description=biosample_fields["biosample_description"].value or None,
            biosample_organism=biosample_fields["biosample_organism"].value or None,
            number_of_cell_lines_used=biosample_fields["number_of_cell_lines_used"].value or None,
        )

        study_updated_library = Library(
            library_file_name=library_fields["library_file_name"].value or None,
            library_file_format=library_fields["library_file_format"].value or None,
            library_type=library_fields["library_type"].value or None,
            library_manufacturer=library_fields["library_manufacturer"].value or None,
            library_version=library_fields["library_version"].value or None,
            library_experimental_conditions=library_fields["library_experimental_conditions"].value
            or None,
            quality_control_description=library_fields["quality_control_description"].value or None,
        )

        study_updated_protocols = Protocols(
            hcs_library_protocol=protocols_fields["hcs_library_protocol"].value or None,
            growth_protocol=protocols_fields["growth_protocol"].value or None,
            treatment_protocol=protocols_fields["treatment_protocol"].value or None,
            hcs_data_analysis_protocol=protocols_fields["hcs_data_analysis_protocol"].value or None,
        )

        study_updated_plate = Plate(
            plate_type=plate_fields["plate_type"].value or None,
            plate_type_manufacturer=plate_fields["plate_type_manufacturer"].value or None,
            plate_type_catalog_number=plate_fields["plate_type_catalog_number"].value or None,
        )
    return (
        study_updated_biosample,
        study_updated_library,
        study_updated_plate,
        study_updated_protocols,
        study_updated_study,
    )


@app.cell
def _(
    Assay,
    AssayComponent,
    BiosampleAssay,
    ImageAcquisition,
    ImageData,
    metadata,
    mo,
):
    """Create Assay Information forms."""
    if metadata is None:
        assay_fields = None
        assay_component_fields = None
        biosample_assay_fields = None
        image_data_fields = None
        image_acquisition_fields = None
        specimen_channel_transmission_field = None
        specimen_channel_dicts = None
        assay_forms = None
    else:
        # Assay form
        _current_assay = metadata.assay_information.assay if metadata.assay_information else None
        assay_fields = create_pydantic_form(mo, Assay, _current_assay)
        _assay_form = mo.vstack(
            [
                mo.md("**Assay Information**"),
                assay_fields["assay_title"],
                assay_fields["assay_internal_id"],
                assay_fields["assay_description"],
                assay_fields["assay_number_of_biological_replicates"],
                assay_fields["number_of_plates"],
                assay_fields["assay_technology_type"],
                assay_fields["assay_type"],
                assay_fields["assay_external_url"],
                assay_fields["assay_data_url"],
            ]
        )

        # AssayComponent form
        _current_assay_component = (
            metadata.assay_information.assay_component if metadata.assay_information else None
        )
        assay_component_fields = create_pydantic_form(mo, AssayComponent, _current_assay_component)
        _assay_component_form = mo.vstack(
            [
                mo.md("**Assay Component**"),
                assay_component_fields["imaging_protocol"],
                assay_component_fields["sample_preparation_protocol"],
            ]
        )

        # BiosampleAssay form
        _current_biosample_assay = (
            metadata.assay_information.biosample if metadata.assay_information else None
        )
        biosample_assay_fields = create_pydantic_form(mo, BiosampleAssay, _current_biosample_assay)
        _biosample_assay_form = mo.vstack(
            [
                mo.md("**Biosample (Assay)**"),
                biosample_assay_fields["cell_lines_storage_location"],
                biosample_assay_fields["cell_lines_clone_number"],
                biosample_assay_fields["cell_lines_passage_number"],
            ]
        )

        # ImageData form
        _current_image_data = (
            metadata.assay_information.image_data if metadata.assay_information else None
        )
        image_data_fields = create_pydantic_form(mo, ImageData, _current_image_data)
        _image_data_form = mo.vstack(
            [
                mo.md("**Image Data**"),
                image_data_fields["image_number_of_pixelsx"],
                image_data_fields["image_number_of_pixelsy"],
                image_data_fields["image_number_of_z_stacks"],
                image_data_fields["image_number_of_channels"],
                image_data_fields["image_number_of_timepoints"],
                image_data_fields["image_sites_per_well"],
            ]
        )

        # ImageAcquisition form
        _current_image_acquisition = (
            metadata.assay_information.image_acquisition if metadata.assay_information else None
        )
        image_acquisition_fields = create_pydantic_form(
            mo, ImageAcquisition, _current_image_acquisition
        )
        _image_acquisition_form = mo.vstack(
            [
                mo.md("**Image Acquisition**"),
                image_acquisition_fields["microscope_id"],
            ]
        )

        # Specimen form (special handling for channels)
        _current_specimen = (
            metadata.assay_information.specimen if metadata.assay_information else None
        )

        specimen_channel_transmission_field = mo.ui.text(
            label="Channel Transmission ID",
            value=_current_specimen.channel_transmission_id or "" if _current_specimen else "",
            placeholder="Channel id dependent on different machines",
        )

        # Create channel forms - simplified approach using dictionaries
        _existing_channels = _current_specimen.channels if _current_specimen else []

        def _create_channel_dict(channel=None):
            return {
                "visualization_method": mo.ui.text(
                    label="Visualization Method",
                    value=channel.visualization_method or "" if channel else "",
                    placeholder="e.g., Hoechst staining, GFP",
                ),
                "entity": mo.ui.text(
                    label="Entity",
                    value=channel.entity or "" if channel else "",
                    placeholder="e.g., DNA, MAP1LC3B",
                ),
                "label": mo.ui.text(
                    label="Label",
                    value=channel.label or "" if channel else "",
                    placeholder="e.g., Nuclei, GFP-LC3",
                ),
                "id": mo.ui.text(
                    label="ID",
                    value=channel.id or "" if channel else "",
                    placeholder="Channel order in image",
                ),
            }

        # Create up to 8 channel forms (fixed slots for simplicity)
        _specimen_channel_forms = []
        for i in range(8):
            ch = _existing_channels[i] if i < len(_existing_channels) else None
            _ch_dict = _create_channel_dict(ch)

            # Create a form for this channel
            _ch_form = mo.vstack(
                [
                    mo.md(f"**Channel {i + 1}**"),
                    _ch_dict["visualization_method"],
                    _ch_dict["entity"],
                    _ch_dict["label"],
                    _ch_dict["id"],
                ]
            )
            _specimen_channel_forms.append((i, _ch_dict, _ch_form))

        # Store the channel dictionaries for later access
        specimen_channel_dicts = [item[1] for item in _specimen_channel_forms]

        # Create accordion for channels
        _channels_accordion = mo.accordion(
            {f"Channel {i + 1}": item[2] for i, item in enumerate(_specimen_channel_forms)}
        )

        _specimen_form = mo.vstack(
            [
                mo.md("**Specimen/Channels**"),
                specimen_channel_transmission_field,
                mo.md("*Fluorescence Channels (expand to edit):*"),
                _channels_accordion,
            ]
        )

        # Combine into tabs
        assay_forms = mo.ui.tabs(
            {
                "Assay": _assay_form,
                "Assay Component": _assay_component_form,
                "Biosample": _biosample_assay_form,
                "Image Data": _image_data_form,
                "Image Acquisition": _image_acquisition_form,
                "Specimen": _specimen_form,
            }
        ).form(label="Update Assay Information", bordered=True)
    return (
        assay_component_fields,
        assay_fields,
        assay_forms,
        biosample_assay_fields,
        image_acquisition_fields,
        image_data_fields,
        specimen_channel_dicts,
        specimen_channel_transmission_field,
    )


@app.cell
def _(
    Assay,
    AssayComponent,
    BiosampleAssay,
    Channel,
    ImageAcquisition,
    ImageData,
    Specimen,
    assay_component_fields,
    assay_fields,
    assay_forms,
    biosample_assay_fields,
    image_acquisition_fields,
    image_data_fields,
    specimen_channel_dicts,
    specimen_channel_transmission_field,
):
    """Process Assay Information form submission."""
    assay_updated_assay = None
    assay_updated_assay_component = None
    assay_updated_biosample_assay = None
    assay_updated_image_data = None
    assay_updated_image_acquisition = None
    assay_updated_specimen = None

    if assay_forms is not None and assay_forms.value:
        assay_updated_assay = Assay(
            assay_title=assay_fields["assay_title"].value or None,
            assay_internal_id=assay_fields["assay_internal_id"].value or None,
            assay_description=assay_fields["assay_description"].value or None,
            assay_number_of_biological_replicates=assay_fields[
                "assay_number_of_biological_replicates"
            ].value
            or None,
            number_of_plates=assay_fields["number_of_plates"].value or None,
            assay_technology_type=assay_fields["assay_technology_type"].value or None,
            assay_type=assay_fields["assay_type"].value or None,
            assay_external_url=assay_fields["assay_external_url"].value or None,
            assay_data_url=assay_fields["assay_data_url"].value or None,
        )

        assay_updated_assay_component = AssayComponent(
            imaging_protocol=assay_component_fields["imaging_protocol"].value or None,
            sample_preparation_protocol=assay_component_fields["sample_preparation_protocol"].value
            or None,
        )

        assay_updated_biosample_assay = BiosampleAssay(
            cell_lines_storage_location=biosample_assay_fields["cell_lines_storage_location"].value
            or None,
            cell_lines_clone_number=biosample_assay_fields["cell_lines_clone_number"].value or None,
            cell_lines_passage_number=biosample_assay_fields["cell_lines_passage_number"].value
            or None,
        )

        assay_updated_image_data = ImageData(
            image_number_of_pixelsx=image_data_fields["image_number_of_pixelsx"].value or None,
            image_number_of_pixelsy=image_data_fields["image_number_of_pixelsy"].value or None,
            image_number_of_z_stacks=image_data_fields["image_number_of_z_stacks"].value or None,
            image_number_of_channels=image_data_fields["image_number_of_channels"].value or None,
            image_number_of_timepoints=image_data_fields["image_number_of_timepoints"].value
            or None,
            image_sites_per_well=image_data_fields["image_sites_per_well"].value or None,
        )

        assay_updated_image_acquisition = ImageAcquisition(
            microscope_id=image_acquisition_fields["microscope_id"].value or None,
        )

        # Process channels from the 8 channel dictionaries
        _processed_channels = []
        if specimen_channel_dicts is not None:
            for _channel_dict in specimen_channel_dicts:
                _vis_method = _channel_dict["visualization_method"].value or None
                _entity = _channel_dict["entity"].value or None
                _label = _channel_dict["label"].value or None
                _ch_id = _channel_dict["id"].value or None

                # Only add channel if it has any data
                if any([_vis_method, _entity, _label, _ch_id]):
                    _processed_channels.append(
                        Channel(
                            visualization_method=_vis_method,
                            entity=_entity,
                            label=_label,
                            id=_ch_id,
                        )
                    )

        assay_updated_specimen = Specimen(
            channel_transmission_id=specimen_channel_transmission_field.value or None,
            channels=_processed_channels,
        )
    return (
        assay_updated_assay,
        assay_updated_assay_component,
        assay_updated_biosample_assay,
        assay_updated_image_acquisition,
        assay_updated_image_data,
        assay_updated_specimen,
    )


@app.cell(hide_code=True)
def _(
    assay_forms,
    inv_investigation_forms,
    inv_updated_collaborators,
    inv_updated_data_owner,
    inv_updated_investigation_info,
    metadata,
    mo,
    study_forms,
):
    """Build metadata tab content with nested tabs."""
    if metadata is None:
        metadata_tab_content = mo.callout(
            mo.md("**Please load a template first** in the Load Template tab."), kind="warn"
        )
    else:
        # Build Investigation sub-tab content
        if inv_updated_data_owner is not None and inv_updated_investigation_info is not None:
            _inv_result = mo.accordion(
                {
                    "Updated Data Owner": mo.plain(inv_updated_data_owner),
                    "Updated Investigation Info": mo.plain(inv_updated_investigation_info),
                    "Updated Collaborators": mo.plain(inv_updated_collaborators),
                }
            )
        else:
            _inv_result = mo.md("*Submit the form to see updated values*")

        _investigation_tab_content = mo.vstack(
            [
                mo.md("""
            **Investigation-level metadata** (who, what, why)

            Fill in data owner, investigation details, and collaborators.
            """),
                inv_investigation_forms,
                _inv_result,
            ],
            gap=2,
        )

        # Build Study sub-tab content
        _study_tab_content = mo.vstack(
            [
                mo.md("""
            **Study-level metadata**

            Details about the study, biosample, library, protocols, and plate configuration.
            """),
                study_forms if study_forms is not None else mo.md("*Forms not loaded*"),
            ],
            gap=2,
        )

        # Build Assay sub-tab content
        _assay_tab_content = mo.vstack(
            [
                mo.md("""
            **Assay-level metadata**

            Assay details, imaging protocols, image data, and specimen/channel information.
            """),
                assay_forms if assay_forms is not None else mo.md("*Forms not loaded*"),
            ],
            gap=2,
        )

        # Create nested tabs structure
        _metadata_nested_tabs = mo.ui.tabs(
            {
                "Investigation": _investigation_tab_content,
                "Study": _study_tab_content,
                "Assay": _assay_tab_content,
            }
        )

        # Assemble the Metadata tab content
        metadata_tab_content = mo.vstack(
            [
                mo.md("""
            ### Edit Metadata

            Edit all levels of MIHCSME metadata organized by Investigation, Study, and Assay.
            """),
                _metadata_nested_tabs,
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
    AssayInformation,
    InvestigationInformation,
    StudyInformation,
    assay_updated_assay,
    assay_updated_assay_component,
    assay_updated_biosample_assay,
    assay_updated_image_acquisition,
    assay_updated_image_data,
    assay_updated_specimen,
    export_button,
    export_filename,
    inv_updated_collaborators,
    inv_updated_data_owner,
    inv_updated_investigation_info,
    io,
    metadata_updated,
    mo,
    study_updated_biosample,
    study_updated_library,
    study_updated_plate,
    study_updated_protocols,
    study_updated_study,
    write_metadata_to_excel,
):
    export_result = None
    download_button = None
    if export_button.value:
        try:
            _final_metadata = metadata_updated.model_copy(deep=True)

            try:
                # Update Investigation Information
                if (
                    inv_updated_data_owner is not None
                    and inv_updated_investigation_info is not None
                ):
                    _updated_investigation_information = InvestigationInformation(
                        data_owner=inv_updated_data_owner,
                        investigation_info=inv_updated_investigation_info,
                        data_collaborators=inv_updated_collaborators,
                    )
                    _final_metadata.investigation_information = _updated_investigation_information

                # Update Study Information
                if study_updated_study is not None:
                    _updated_study_information = StudyInformation(
                        study=study_updated_study,
                        biosample=study_updated_biosample,
                        library=study_updated_library,
                        protocols=study_updated_protocols,
                        plate=study_updated_plate,
                    )
                    _final_metadata.study_information = _updated_study_information

                # Update Assay Information
                if assay_updated_assay is not None:
                    _updated_assay_information = AssayInformation(
                        assay=assay_updated_assay,
                        assay_component=assay_updated_assay_component,
                        biosample=assay_updated_biosample_assay,
                        image_data=assay_updated_image_data,
                        image_acquisition=assay_updated_image_acquisition,
                        specimen=assay_updated_specimen,
                    )
                    _final_metadata.assay_information = _updated_assay_information
            except NameError:
                pass

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
    omero_upload_button = mo.ui.run_button(label="Upload Metadata to OMERO")
    return (
        omero_upload_button,
        omero_upload_replace,
        omero_upload_target_id,
        omero_upload_target_type,
    )


@app.cell
def _(
    AssayInformation,
    InvestigationInformation,
    StudyInformation,
    assay_updated_assay,
    assay_updated_assay_component,
    assay_updated_biosample_assay,
    assay_updated_image_acquisition,
    assay_updated_image_data,
    assay_updated_specimen,
    get_omero_conn,
    inv_updated_collaborators,
    inv_updated_data_owner,
    inv_updated_investigation_info,
    metadata_updated,
    mo,
    omero_upload_button,
    omero_upload_replace,
    omero_upload_target_id,
    omero_upload_target_type,
    study_updated_biosample,
    study_updated_library,
    study_updated_plate,
    study_updated_protocols,
    study_updated_study,
    upload_metadata_to_omero,
):
    # OMERO Upload Handler
    omero_upload_result = None
    omero_upload_error = None

    if omero_upload_button.value:
        _conn = get_omero_conn()
        if _conn is None:
            omero_upload_error = "Not connected to OMERO. Please connect first."
        elif metadata_updated is None:
            omero_upload_error = "No metadata to upload. Please load a template first."
        else:
            try:
                # Build final metadata with any form updates
                _final_metadata = metadata_updated.model_copy(deep=True)

                try:
                    # Update Investigation Information
                    if (
                        inv_updated_data_owner is not None
                        and inv_updated_investigation_info is not None
                    ):
                        _updated_investigation_information = InvestigationInformation(
                            data_owner=inv_updated_data_owner,
                            investigation_info=inv_updated_investigation_info,
                            data_collaborators=inv_updated_collaborators,
                        )
                        _final_metadata.investigation_information = (
                            _updated_investigation_information
                        )

                    # Update Study Information
                    if study_updated_study is not None:
                        _updated_study_information = StudyInformation(
                            study=study_updated_study,
                            biosample=study_updated_biosample,
                            library=study_updated_library,
                            protocols=study_updated_protocols,
                            plate=study_updated_plate,
                        )
                        _final_metadata.study_information = _updated_study_information

                    # Update Assay Information
                    if assay_updated_assay is not None:
                        _updated_assay_information = AssayInformation(
                            assay=assay_updated_assay,
                            assay_component=assay_updated_assay_component,
                            biosample=assay_updated_biosample_assay,
                            image_data=assay_updated_image_data,
                            image_acquisition=assay_updated_image_acquisition,
                            specimen=assay_updated_specimen,
                        )
                        _final_metadata.assay_information = _updated_assay_information
                except NameError:
                    pass

                # Upload to OMERO
                _result = upload_metadata_to_omero(
                    conn=_conn,
                    metadata=_final_metadata,
                    target_type=omero_upload_target_type.value,
                    target_id=int(omero_upload_target_id.value),
                    replace=omero_upload_replace.value,
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
                    omero_upload_error = _result["message"]

            except Exception as e:
                omero_upload_error = str(e)

    # Build upload status display
    if omero_upload_error:
        omero_upload_display = mo.callout(
            mo.md(f"**Upload Error:** {omero_upload_error}"), kind="danger"
        )
    elif omero_upload_result:
        if "Partial" in omero_upload_result:
            omero_upload_display = mo.callout(mo.md(f"**{omero_upload_result}**"), kind="warn")
        else:
            omero_upload_display = mo.callout(mo.md(f"**{omero_upload_result}**"), kind="success")
    else:
        omero_upload_display = mo.md("")
    return (omero_upload_display,)


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
    omero_upload_target_id,
    omero_upload_target_type,
    omero_user,
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
            """),
            mo.hstack([omero_upload_target_type, omero_upload_target_id], gap=2),
            omero_upload_replace,
            omero_upload_button,
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
