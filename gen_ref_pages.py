"""Generate the code reference pages for mkdocstrings."""

from pathlib import Path

import mkdocs_gen_files

nav = mkdocs_gen_files.Nav()

src_path = Path("src")
package_path = src_path / "mihcsme_py"

for path in sorted(package_path.rglob("*.py")):
    module_path = path.relative_to(src_path).with_suffix("")
    doc_path = path.relative_to(src_path).with_suffix(".md")
    full_doc_path = Path("api", doc_path)

    parts = tuple(module_path.parts)

    # Skip __pycache__ and private modules
    if "__pycache__" in parts or any(p.startswith("_") and p != "__init__.py" for p in parts):
        continue

    # Skip __init__.py files (they're included in parent module)
    if parts[-1] == "__init__":
        continue

    nav[parts] = doc_path.as_posix()

    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        ident = ".".join(parts)
        fd.write(f"# {ident}\n\n")
        fd.write(f"::: {ident}\n")

    mkdocs_gen_files.set_edit_path(full_doc_path, path)

# Generate the navigation index
with mkdocs_gen_files.open("api/index.md", "w") as nav_file:
    nav_file.write("# API Reference\n\n")
    nav_file.write("This section contains the API reference for the MIHCSME OMERO package.\n\n")
    nav_file.write("## Modules\n\n")

    # List main modules
    modules = [
        ("models", "Pydantic models for MIHCSME metadata"),
        ("parser", "Excel to Pydantic model parsing"),
        ("writer", "Pydantic model to Excel conversion"),
        ("uploader", "Upload metadata to OMERO"),
        ("cli", "Command-line interface"),
    ]

    for module, description in modules:
        nav_file.write(f"- [`mihcsme_py.{module}`](mihcsme_py/{module}.md): {description}\n")
