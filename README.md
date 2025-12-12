# MIHCSME OMERO

Convert MIHCSME (Minimum Information about a High Content Screening Microscopy Experiment) metadata from Excel spreadsheets to validated Pydantic models and upload to OMERO.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Parse MIHCSME Excel files** into type-safe Pydantic models
- **Automatic validation** with clear error messages
- **Bidirectional conversion** between Excel, Pydantic, and OMERO key-pair value format
- **Modern CLI** with rich terminal output

## Installation

### Development Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/MIHCSME_OMERO.git
cd MIHCSME_OMERO

# Create virtual environment with uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with dev dependencies
uv pip install -e ".[dev]"
```

### User Installation (After PyPI Release)

```bash
uv pip install mihcsme-omero
```

## Quick Start

### Command Line

```bash
# Validate MIHCSME Excel file
mihcsme validate LEI-MIHCSME.xlsx

# Parse Excel to JSON
mihcsme parse LEI-MIHCSME.xlsx --output metadata.json

# Upload to OMERO Screen
mihcsme upload LEI-MIHCSME.xlsx \
    --screen-id 123 \
    --host omero.example.com \
    --user myuser

# Upload with replace (removes existing annotations)
mihcsme upload LEI-MIHCSME.xlsx \
    --plate-id 456 \
    --host omero.example.com \
    --user myuser \
    --replace
```

### Python API

```python
from pathlib import Path
from mihcsme_omero import connect, parse_excel_to_model, upload_metadata_to_omero

# Parse Excel file to Pydantic model
excel_path = Path("LEI-MIHCSME.xlsx")
metadata = parse_excel_to_model(excel_path)

# Inspect the model
print(f"Wells: {len(metadata.assay_conditions)}")
for condition in metadata.assay_conditions:
    print(f"{condition.plate} / {condition.well}: {condition.conditions}")

# Connect to OMERO
conn = connect(
    host="omero.example.com",
    user="myuser",
    password="mypassword",
    port=4064,
    secure=True,
)

# Upload to OMERO
result = upload_metadata_to_omero(
    conn=conn,
    metadata=metadata,
    target_type="Screen",
    target_id=123,
    namespace="MIHCSME",
    replace=False,
)

print(f"Status: {result['status']}")
print(f"Wells succeeded: {result['wells_succeeded']}")

conn.close()
```

## Excel File Structure

The MIHCSME Excel file should contain these sheets:

- **InvestigationInformation** - Investigation-level metadata (grouped key-value pairs)
- **StudyInformation** - Study-level metadata (grouped key-value pairs)
- **AssayInformation** - Assay-level metadata (grouped key-value pairs)
- **AssayConditions** - Per-well metadata (tabular: Plate, Well, conditions...)
- **_Reference sheets** - Reference data (sheets starting with `_`)

See [LEI-MIHCSME.xlsx](LEI-MIHCSME.xlsx) for an example.

## Data Model

The package uses Pydantic models for type-safe metadata handling:

```python
from mihcsme_omero.models import MIHCSMEMetadata, AssayCondition

# Create metadata programmatically
metadata = MIHCSMEMetadata(
    assay_conditions=[
        AssayCondition(
            plate="Plate1",
            well="A1",  # Automatically normalized to "A01"
            conditions={"Compound": "DMSO", "Concentration": "0.1%"},
        )
    ]
)

# Convert to OMERO dict format
omero_dict = metadata.to_omero_dict()

# Create from OMERO dict format
metadata = MIHCSMEMetadata.from_omero_dict(omero_dict)
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=mihcsme_omero --cov-report=html

# Run type checking
mypy src/mihcsme_omero

# Format code
black src/ tests/

# Lint code
ruff check src/ tests/ --fix
```

### Project Structure

```
mihcsme-omero/
├── src/mihcsme_omero/          # Source code (src layout)
│   ├── __init__.py              # Package exports
│   ├── models.py                # Pydantic models
│   ├── parser.py                # Excel → Pydantic
│   ├── omero_connection.py      # OMERO connection utilities
│   ├── uploader.py              # Pydantic → OMERO
│   └── cli.py                   # Typer CLI
├── tests/                       # Test suite
├── original_scripts/            # Legacy scripts (reference only)
├── pyproject.toml               # Package configuration
├── README.md                    # This file
└── CLAUDE.md                    # Developer documentation
```

## Documentation

- [CLAUDE.md](CLAUDE.md) - Comprehensive developer documentation
- [LEI-MIHCSME.xlsx](LEI-MIHCSME.xlsx) - Example MIHCSME Excel file

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make changes with tests
4. Run quality checks (`black`, `ruff`, `mypy`, `pytest`)
5. Commit with clear message
6. Push and create pull request

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Technology Stack

- **omero-py** - Direct OMERO server integration
- **Pydantic** - Data validation and models
- **Pandas** - Excel file parsing
- **Typer** - Modern CLI framework
- **Rich** - Beautiful terminal output

## References

- [OMERO Documentation](https://docs.openmicroscopy.org/omero/)
- [OMERO Python Language Bindings](https://github.com/ome/omero-py)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Typer Documentation](https://typer.tiangolo.com/)
- [MIHCSME Specification](https://www.ebi.ac.uk/biosamples/docs/references/sampletab)
