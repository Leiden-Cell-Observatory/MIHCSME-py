import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 🧬 MIHCSME Metadata Editor

    *Create and edit metadata templates for high-content screening microscopy experiments*

    ---
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 📁 Step 1: Load Template

    Choose how to load your MIHCSME metadata:
    - **File Path**: Specify a path to an existing Excel file
    - **Upload File**: Upload an Excel file from your computer
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    file_source = mo.ui.radio(
        options=["File Path", "Upload File"],
        value="File Path",
        label="How do you want to load the Excel file?"
    )
    file_source
    return (file_source,)


@app.cell
def _(file_source, mo):
    if file_source.value == "File Path":
        path_input = mo.ui.text(
            value="MIHCSME Template_example.xlsx",
            label="Excel file path:",
            full_width=True
        )
        file_upload = None
        result = path_input
    else:
        file_upload = mo.ui.file(
            label="Upload Excel file:",
            filetypes=[".xlsx"]
        )
        path_input = None
        result = file_upload

    result
    return file_upload, path_input


@app.cell
def _(Path, file_source, file_upload, parse_excel_to_model, path_input):
    metadata = None
    if file_source.value == "File Path":
        if path_input is not None and path_input.value:
            excel_path = Path(path_input.value)
            metadata = parse_excel_to_model(excel_path)
    else:
        # file_upload.value is a list of file objects when files are uploaded
        if file_upload is not None and len(file_upload.value) > 0:
            # Pass the bytes directly - parser now accepts bytes
            metadata = parse_excel_to_model(file_upload.contents())

    metadata
    return (metadata,)


@app.cell
def _(metadata, mo):
    if metadata is not None:
        _num_conditions = len(metadata.assay_conditions) if metadata.assay_conditions else 0
        _status = mo.md(f"✅ **Template loaded successfully!** ({_num_conditions} well conditions found)")
    else:
        _status = mo.md("⚪ No template loaded yet - use the controls above")

    _status
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 🧪 Step 2: Edit Plates & Wells

    View and modify well-level metadata across your plates.

    **TODO for future:**
    1. Make it possible to add new plates
    2. Add forms for Study and Assay metadata
    """)
    return


@app.cell
def _(metadata, mo):
    mo.stop(metadata is None)
    # Create state to hold the current dataframe (allows updates)
    df = metadata.to_dataframe()
    return (df,)


@app.cell
def _(column_select, format_select, mo, plate_select):
    # Display the controls
    controls = mo.hstack([plate_select, column_select, format_select])
    controls
    return


@app.cell
def _(column_select, df, format_select, mo, plate_select, visualize_plate):
    # Generate plate visualization based on selections
    if column_select.value and plate_select.value:
        plate_html = visualize_plate(
            df,
            column_select.value,
            plate_select.value,
            format_select.value
        )
        plate_viz = mo.Html(plate_html)
    else:
        plate_viz = mo.md("Select a column and plate to visualize")

    plate_viz
    return


@app.cell
def _(df, mo):
    editor = mo.ui.data_editor(df)
    editor
    return (editor,)


@app.cell
def _(editor, metadata):
    metadata_updated = metadata.update_conditions_from_dataframe(editor.value)
    df_updated = metadata_updated.to_dataframe()
    df_updated
    return df_updated, metadata_updated


@app.cell
def _(
    column_select,
    df_updated,
    format_select,
    mo,
    plate_select,
    visualize_plate,
):
    plate_html2 = visualize_plate(
        df_updated,
        column_select.value,
        plate_select.value,
        format_select.value
    )
    mo.Html(plate_html2)
    return


@app.cell(hide_code=True)
def _():
    import pandas as pd
    import numpy as np

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
            plate_df = df[df['Plate'] == plate_name].copy()
        else:
            # Use first plate if not specified
            plate_name = df['Plate'].iloc[0] if len(df) > 0 else "Unknown"
            plate_df = df[df['Plate'] == plate_name].copy()

        # Parse well positions (e.g., "A01" -> row="A", col=1)
        def parse_well(well_str):
            row = well_str[0]  # Letter (A-P)
            col = int(well_str[1:])  # Number (1-48)
            return row, col

        # Create lookup dictionary for data
        well_data_dict = {}
        if len(plate_df) > 0:
            plate_df['row'] = plate_df['Well'].apply(lambda w: parse_well(w)[0])
            plate_df['col'] = plate_df['Well'].apply(lambda w: parse_well(w)[1])

            for _, row_data in plate_df.iterrows():
                key = (row_data['row'], row_data['col'])
                well_data_dict[key] = row_data[column_to_display]

        # Create HTML table
        html = f"<h3>Plate: {plate_name} - {column_to_display} ({plate_format}-well)</h3>"
        html += "<table style='border-collapse: collapse; font-family: monospace; font-size: 10px;'>"

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


@app.cell(hide_code=True)
def _(df, mo):
    # Get available columns (excluding Plate and Well)
    data_columns = [col for col in df.columns if col not in ['Plate', 'Well']]

    # Get unique plates
    plates = df['Plate'].unique().tolist() if len(df) > 0 else []

    # Create interactive controls
    column_select = mo.ui.dropdown(
        options=data_columns,
        value=data_columns[0] if data_columns else None,
        label="Column to display:"
    )

    plate_select = mo.ui.dropdown(
        options=plates,
        value=plates[0] if plates else None,
        label="Plate:"
    )

    format_select = mo.ui.dropdown(
        options=["96", "384"],
        value="96",
        label="Plate format:"
    )
    return column_select, format_select, plate_select


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 📋 Step 3: Edit Metadata

    Edit investigation-level metadata (who, what, why).

    *More metadata forms (Study, Assay) will be added in future updates.*
    """)
    return


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
            placeholder=description[:50] if description else ""
        )
    return form_fields


@app.cell(hide_code=True)
def _(DataOwner, InvestigationInfo, metadata, mo):
    mo.stop(
        metadata is None,
        mo.md("⚠️ **Please load a template first**")
    )

    current_data_owner = metadata.investigation_information.data_owner if metadata.investigation_information else None
    data_owner_fields = create_pydantic_form(mo, DataOwner, current_data_owner)

    data_owner_form = mo.vstack([
        mo.md("**Data Owner Information**"),
        data_owner_fields["first_name"],
        data_owner_fields["middle_names"],
        data_owner_fields["last_name"],
        data_owner_fields["user_name"],
        data_owner_fields["institute"],
        data_owner_fields["email"],
        data_owner_fields["orcid"],
    ])

    current_investigation_info = metadata.investigation_information.investigation_info if metadata.investigation_information else None
    investigation_info_fields = create_pydantic_form(mo, InvestigationInfo, current_investigation_info)

    investigation_info_form = mo.vstack([
        mo.md("**Investigation Information**"),
        investigation_info_fields["project_id"],
        investigation_info_fields["investigation_title"],
        investigation_info_fields["investigation_internal_id"],
        investigation_info_fields["investigation_description"],
    ])

    investigation_tabs = mo.ui.tabs({
        "Data Owner": data_owner_form,
        "Investigation Info": investigation_info_form,
    }).form(label="Update Investigation Information", bordered=True)

    investigation_tabs
    return data_owner_fields, investigation_info_fields, investigation_tabs


@app.cell
def _(metadata, mo):
    mo.stop(
        metadata is None,
        mo.md("""
        ⚠️ **No template loaded**

        Please load a template in Step 1 first.
        """)
    )
    return


@app.cell
def _(
    DataOwner,
    InvestigationInfo,
    data_owner_fields,
    investigation_info_fields,
    investigation_tabs,
    mo,
):
    updated_data_owner = None
    updated_investigation_info = None

    if investigation_tabs.value:
        updated_data_owner = DataOwner(
            first_name=data_owner_fields["first_name"].value or None,
            middle_names=data_owner_fields["middle_names"].value or None,
            last_name=data_owner_fields["last_name"].value or None,
            user_name=data_owner_fields["user_name"].value or None,
            institute=data_owner_fields["institute"].value or None,
            email=data_owner_fields["email"].value or None,
            orcid=data_owner_fields["orcid"].value or None,
        )

        updated_investigation_info = InvestigationInfo(
            project_id=investigation_info_fields["project_id"].value or None,
            investigation_title=investigation_info_fields["investigation_title"].value or None,
            investigation_internal_id=investigation_info_fields["investigation_internal_id"].value or None,
            investigation_description=investigation_info_fields["investigation_description"].value or None,
        )

        _form_result = mo.vstack([
            mo.md("**Updated Data Owner:**"),
            updated_data_owner,
            mo.md("**Updated Investigation Info:**"),
            updated_investigation_info,
        ])
    else:
        _form_result = mo.md("*Submit the form above to see updated values*")

    _form_result
    return updated_data_owner, updated_investigation_info


@app.cell
def _(mo):
    mo.md(r"""
    ## 💾 Step 4: Review & Export

    Save your completed metadata template to Excel format.
    """)
    return


@app.cell
def _(metadata_updated, mo):
    if metadata_updated:
        _summary_df = metadata_updated.to_dataframe()
        _num_plates = len(_summary_df['Plate'].unique()) if len(_summary_df) > 0 else 0
        _num_wells = len(_summary_df)

        _summary = mo.md(f"""
        ### Summary
        - **Plates:** {_num_plates}
        - **Wells:** {_num_wells}
        - **Investigation Info:** {"✓" if metadata_updated.investigation_information else "✗"}
        """)
    else:
        _summary = mo.md("*No metadata to display*")

    _summary
    return


@app.cell
def _(mo):
    export_filename = mo.ui.text(
        value="MIHCSME_export.xlsx",
        label="Output filename:",
        full_width=True
    )
    export_button = mo.ui.run_button(label="Export to Excel")

    mo.vstack([export_filename, export_button])
    return export_button, export_filename


@app.cell
def _(
    InvestigationInformation,
    Path,
    export_button,
    export_filename,
    metadata_updated,
    mo,
    updated_data_owner,
    updated_investigation_info,
    write_metadata_to_excel,
):
    mo.stop(not export_button.value)

    try:
        _final_metadata = metadata_updated.model_copy(deep=True)

        try:
            if updated_data_owner is not None and updated_investigation_info is not None:
                _updated_investigation_information = InvestigationInformation(
                    data_owner=updated_data_owner,
                    investigation_info=updated_investigation_info,
                )
                _final_metadata.investigation_information = _updated_investigation_information
        except NameError:
            pass

        _output_path = Path(export_filename.value)
        write_metadata_to_excel(_final_metadata, _output_path)

        _export_result = mo.md(f"✅ **Successfully exported to:** `{_output_path}`")
    except Exception as e:
        _export_result = mo.md(f"❌ **Error exporting:** {str(e)}")

    _export_result
    return


@app.cell
def _():
    import marimo as mo
    from io import BytesIO
    from mihcsme_py import (
        parse_excel_to_model,
        upload_metadata_to_omero,
        download_metadata_from_omero,
        write_metadata_to_excel,
    )
    from mihcsme_py.models import (
        MIHCSMEMetadata,
        AssayCondition,
        InvestigationInformation,
        InvestigationInfo,
        StudyInformation,
        AssayInformation,
        DataOwner,
    )
    from pathlib import Path
    from pydantic import BaseModel
    from typing import Optional
    return (
        DataOwner,
        InvestigationInfo,
        InvestigationInformation,
        Path,
        mo,
        parse_excel_to_model,
        write_metadata_to_excel,
    )


if __name__ == "__main__":
    app.run()
