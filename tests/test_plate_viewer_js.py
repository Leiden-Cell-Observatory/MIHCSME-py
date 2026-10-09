"""Static checks on the plate viewer frontend."""

import re
from pathlib import Path

JS = Path(__file__).parents[1] / "src" / "mihcsme_py" / "widgets" / "plate_viewer.js"


def test_model_values_never_interpolated_into_inner_html():
    # Field names and values come from user Excel/OMERO data: insert them as text, not HTML.
    source = JS.read_text()
    for match in re.finditer(r"innerHTML\s*=\s*`(.*?)`", source, re.S):
        assert "model.get(" not in match.group(1), match.group(0)[:120]
