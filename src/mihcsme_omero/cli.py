"""Command-line interface for mihcsme-omero."""

import getpass
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from mihcsme_omero import __version__
from mihcsme_omero.omero_connection import connect
from mihcsme_omero.parser import parse_excel_to_model
from mihcsme_omero.uploader import upload_metadata_to_omero

app = typer.Typer(
    name="mihcsme",
    help="Convert MIHCSME metadata from Excel to Pydantic models and upload to OMERO",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"mihcsme-omero version: {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose logging",
    ),
) -> None:
    """MIHCSME OMERO metadata management tool."""
    # Set up logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@app.command()
def parse(
    excel_file: Path = typer.Argument(
        ...,
        help="Path to MIHCSME Excel file",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output JSON file (default: same name as input with .json extension)",
    ),
    validate: bool = typer.Option(
        True,
        "--validate/--no-validate",
        help="Validate the Excel structure",
    ),
) -> None:
    """
    Parse MIHCSME Excel file and convert to JSON (via Pydantic model).

    This validates the Excel structure and outputs a JSON representation
    of the metadata.
    """
    try:
        console.print(f"[bold blue]Parsing Excel file:[/bold blue] {excel_file}")

        # Parse to Pydantic model
        metadata = parse_excel_to_model(excel_file)

        # Determine output path
        if output is None:
            output = excel_file.with_suffix(".json")

        # Convert to dict and save as JSON
        metadata_dict = metadata.model_dump(exclude_none=True)

        with open(output, "w", encoding="utf-8") as f:
            json.dump(metadata_dict, f, indent=2, ensure_ascii=False)

        console.print(f"[bold green]✓[/bold green] Successfully parsed and saved to: {output}")

        # Print summary
        _print_metadata_summary(metadata)

    except Exception as e:
        console.print(f"[bold red]✗ Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def upload(
    excel_file: Path = typer.Argument(
        ...,
        help="Path to MIHCSME Excel file",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
    screen_id: Optional[int] = typer.Option(
        None,
        "--screen-id",
        "-s",
        help="OMERO Screen ID",
    ),
    plate_id: Optional[int] = typer.Option(
        None,
        "--plate-id",
        "-p",
        help="OMERO Plate ID",
    ),
    host: str = typer.Option(
        ...,
        "--host",
        "-H",
        help="OMERO host",
        envvar="OMERO_HOST",
    ),
    user: str = typer.Option(
        ...,
        "--user",
        "-u",
        help="OMERO username",
        envvar="OMERO_USER",
    ),
    port: int = typer.Option(
        4064,
        "--port",
        help="OMERO port",
        envvar="OMERO_PORT",
    ),
    group: Optional[str] = typer.Option(
        None,
        "--group",
        "-g",
        help="OMERO group",
        envvar="OMERO_GROUP",
    ),
    namespace: str = typer.Option(
        "MIHCSME",
        "--namespace",
        "-n",
        help="Base namespace for annotations",
    ),
    replace: bool = typer.Option(
        False,
        "--replace",
        "-r",
        help="Replace existing metadata (remove old annotations first)",
    ),
) -> None:
    """
    Upload MIHCSME metadata from Excel to OMERO.

    You must specify either --screen-id or --plate-id as the target.
    """
    # Validate target specification
    if screen_id is None and plate_id is None:
        console.print("[bold red]✗ Error:[/bold red] Must specify either --screen-id or --plate-id")
        raise typer.Exit(code=1)

    if screen_id is not None and plate_id is not None:
        console.print(
            "[bold red]✗ Error:[/bold red] Cannot specify both --screen-id and --plate-id"
        )
        raise typer.Exit(code=1)

    target_type = "Screen" if screen_id else "Plate"
    target_id = screen_id if screen_id else plate_id

    try:
        # Parse Excel to Pydantic model
        console.print(f"[bold blue]Parsing Excel file:[/bold blue] {excel_file}")
        metadata = parse_excel_to_model(excel_file)
        _print_metadata_summary(metadata)

        # Connect to OMERO
        console.print(f"\n[bold blue]Connecting to OMERO:[/bold blue] {user}@{host}:{port}")
        password = getpass.getpass(f"Password for {user}: ")

        conn = connect(
            host=host,
            user=user,
            password=password,
            port=port,
            group=group,
            secure=True,
        )

        console.print("[bold green]✓[/bold green] Connected to OMERO")

        try:
            # Upload metadata
            console.print(
                f"\n[bold blue]Uploading metadata to {target_type} {target_id}[/bold blue]"
            )
            if replace:
                console.print("[yellow]⚠[/yellow] Replace mode: removing existing annotations...")

            result = upload_metadata_to_omero(
                conn=conn,
                metadata=metadata,
                target_type=target_type,
                target_id=target_id,
                namespace=namespace,
                replace=replace,
            )

            # Print results
            _print_upload_results(result)

            if result["status"] == "error":
                raise typer.Exit(code=1)

        finally:
            conn.close()
            console.print("\n[dim]Connection closed[/dim]")

    except Exception as e:
        console.print(f"\n[bold red]✗ Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def validate(
    excel_file: Path = typer.Argument(
        ...,
        help="Path to MIHCSME Excel file",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """
    Validate MIHCSME Excel file structure.

    Checks that all required sheets are present and properly formatted.
    """
    try:
        console.print(f"[bold blue]Validating:[/bold blue] {excel_file}")

        # Try to parse the file
        metadata = parse_excel_to_model(excel_file)

        console.print("[bold green]✓ File structure is valid[/bold green]")
        _print_metadata_summary(metadata)

    except Exception as e:
        console.print(f"[bold red]✗ Validation failed:[/bold red] {e}")
        raise typer.Exit(code=1)


def _print_metadata_summary(metadata) -> None:
    """Print a summary of the parsed metadata."""
    table = Table(title="Metadata Summary", show_header=True)
    table.add_column("Component", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Details", style="dim")

    # Investigation
    if metadata.investigation_information:
        group_count = len(metadata.investigation_information.groups)
        table.add_row(
            "Investigation Information",
            "[green]✓[/green]",
            f"{group_count} groups",
        )
    else:
        table.add_row("Investigation Information", "[yellow]○[/yellow]", "Not present")

    # Study
    if metadata.study_information:
        group_count = len(metadata.study_information.groups)
        table.add_row(
            "Study Information",
            "[green]✓[/green]",
            f"{group_count} groups",
        )
    else:
        table.add_row("Study Information", "[yellow]○[/yellow]", "Not present")

    # Assay
    if metadata.assay_information:
        group_count = len(metadata.assay_information.groups)
        table.add_row(
            "Assay Information",
            "[green]✓[/green]",
            f"{group_count} groups",
        )
    else:
        table.add_row("Assay Information", "[yellow]○[/yellow]", "Not present")

    # Assay Conditions
    condition_count = len(metadata.assay_conditions)
    if condition_count > 0:
        # Count unique plates
        plates = set(c.plate for c in metadata.assay_conditions)
        table.add_row(
            "Assay Conditions",
            "[green]✓[/green]",
            f"{condition_count} wells, {len(plates)} plates",
        )
    else:
        table.add_row("Assay Conditions", "[yellow]○[/yellow]", "No conditions")

    # Reference Sheets
    ref_count = len(metadata.reference_sheets)
    if ref_count > 0:
        ref_names = ", ".join(r.name for r in metadata.reference_sheets)
        table.add_row(
            "Reference Sheets",
            "[green]✓[/green]",
            f"{ref_count} sheets: {ref_names}",
        )
    else:
        table.add_row("Reference Sheets", "[dim]○[/dim]", "None")

    console.print(table)


def _print_upload_results(result: dict) -> None:
    """Print upload results in a formatted table."""
    status_icon = {
        "success": "[bold green]✓[/bold green]",
        "partial_success": "[yellow]⚠[/yellow]",
        "error": "[bold red]✗[/bold red]",
    }

    icon = status_icon.get(result["status"], "○")
    console.print(f"\n{icon} {result['message']}")

    # Create results table
    table = Table(show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right", style="bold")

    table.add_row("Wells Processed", str(result.get("wells_processed", 0)))
    table.add_row("Wells Succeeded", f"[green]{result.get('wells_succeeded', 0)}[/green]")
    table.add_row("Wells Failed", f"[red]{result.get('wells_failed', 0)}[/red]")

    if result.get("removed_annotations", 0) > 0:
        table.add_row("Annotations Removed", str(result["removed_annotations"]))

    console.print(table)


if __name__ == "__main__":
    app()
