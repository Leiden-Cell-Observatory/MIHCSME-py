# MIHCSME OMERO

A Python package for handling MIHCSME (Minimum Information about a High Content Screening Microscopy Experiment) metadata from Excel spreadsheets to OMERO annotations and back.

## Features

- 📊 Parse MIHCSME Excel files into validated Pydantic models
- 🔄 Bidirectional conversion between Excel, Pydantic, and OMERO formats
- ✅ Built-in validation with helpful error messages
- 🚀 Modern CLI with rich terminal output
- 🐍 Type-safe with full type hints
- 📦 Ready for PyPI distribution

## Installation

### Core Package

Install the minimal package for use in Python scripts or OMERO.scripts:

```bash
pip install mihcsme-py
```

### With CLI Tools

For interactive command-line use:

```bash
pip install mihcsme-py[cli]
```

### Development Installation

For contributors:

```bash
git clone <repository-url>
cd mihcsme_py
source .venv/bin/activate dev
```

## Quick Start

### Parse Excel to JSON

```python
from mihcsme_py import parse_excel_to_model

# Parse Excel file
metadata = parse_excel_to_model("metadata.xlsx")

# Save as JSON
with open("metadata.json", "w") as f:
    f.write(metadata.model_dump_json(indent=2))
```

### Upload to OMERO

```python
import ezomero
from mihcsme_py import parse_excel_to_model, upload_metadata_to_omero

# Parse metadata
metadata = parse_excel_to_model("metadata.xlsx")

# Connect to OMERO
conn = ezomero.connect(
    host="omero.example.com",
    user="myuser",
    password="mypassword"
)

# Upload to screen
result = upload_metadata_to_omero(
    conn=conn,
    metadata=metadata,
    target_type="Screen",
    target_id=123
)

print(f"Uploaded: {result['wells_succeeded']} wells")
conn.close()
```

### CLI Usage

```bash
# Parse Excel to JSON
mihcsme parse metadata.xlsx --output metadata.json

# Upload to OMERO
mihcsme upload metadata.xlsx \
    --screen-id 123 \
    --host omero.example.com \
    --user myuser

# Convert JSON to Excel
mihcsme to-excel metadata.json --output metadata.xlsx
```

## Data Flow

```
Excel (.xlsx) ←→ Pydantic Model ←→ JSON (.json)
                       ↓
                  OMERO Server
```

Supported workflows:

1. **Excel → JSON**: Parse and store metadata in version control
2. **JSON → Excel**: Generate editable templates
3. **Excel → OMERO**: Upload metadata annotations
4. **JSON → OMERO**: Upload from stored metadata

## Architecture

The package provides four main components:

- **`models.py`**: Pydantic models for MIHCSME metadata
- **`parser.py`**: Excel → Pydantic conversion
- **`writer.py`**: Pydantic → Excel conversion
- **`uploader.py`**: Pydantic → OMERO upload
- **`cli.py`**: Command-line interface (optional, requires `[cli]` install)

## Links

- [GitHub Repository](https://github.com/maartenpaul/mihcsme_py)
- [PyPI Package](https://pypi.org/project/mihcsme-omero/)
- [API Reference](api/)
