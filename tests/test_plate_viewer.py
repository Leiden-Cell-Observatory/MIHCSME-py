"""Python-side behaviour of the PlateViewer widget (no browser)."""

import pandas as pd
import pytest

pytest.importorskip("anywidget")

from mihcsme_py.widgets import PlateViewer  # noqa: E402


def _df():
    return pd.DataFrame(
        {
            "Plate": ["P1", "P1", "P2"],
            "Well": ["A01", "A02", "I01"],
            "Treatment": ["DMSO", "CPD1", "DMSO"],
            "Dose": ["0.1", "1", "0.1"],
        }
    )


def test_set_data_populates_traits():
    v = PlateViewer()
    v.set_data(_df())
    assert v.plates == ["P1", "P2"]
    assert v.plate_format == "384"  # I01 forces 384
    assert v.current_plate == "P1"
    assert v.color_field == "Treatment"
    assert len(v.values["P1"]) == 384
    assert v.detail["A01"]["Treatment"] == "DMSO"


def test_changing_color_field_refreshes_values():
    v = PlateViewer()
    v.set_data(_df())
    v.color_field = "Dose"
    assert v.values["P1"][0] == "0.1"


def test_changing_plate_refreshes_detail_and_clears_selection():
    v = PlateViewer()
    v.set_data(_df())
    v.selection = ["A01"]
    v.current_plate = "P2"
    assert set(v.detail) == {"I01"}
    assert v.selection == []


def test_edit_request_applies_and_notifies():
    v = PlateViewer()
    v.set_data(_df())
    seen = []
    v.on_change(seen.append)
    v.edit_request = {"id": 1, "action": "set", "plate": "P1", "wells": ["A01"], "field": "Treatment", "value": "X"}
    assert v.data.loc[0, "Treatment"] == "X"
    assert v.values["P1"][0] == "X"
    assert len(seen) == 1 and seen[0].loc[0, "Treatment"] == "X"
    assert v.can_undo is True


def test_undo_restores_previous():
    v = PlateViewer()
    v.set_data(_df())
    seen = []
    v.on_change(seen.append)
    v.edit_request = {"id": 1, "action": "set", "plate": "P1", "wells": ["A01"], "field": "Treatment", "value": "X"}
    v.edit_request = {"id": 2, "action": "undo"}
    assert v.data.loc[0, "Treatment"] == "DMSO"
    assert v.can_undo is False
    assert seen[-1].loc[0, "Treatment"] == "DMSO"


def test_set_data_with_same_frame_keeps_undo():
    v = PlateViewer()
    v.set_data(_df())
    v.on_change(v.set_data)  # what the app does via mo.state round-trip
    v.edit_request = {"id": 1, "action": "set", "plate": "P1", "wells": ["A01"], "field": "Treatment", "value": "X"}
    assert v.can_undo is True


def test_set_data_with_new_frame_clears_undo():
    v = PlateViewer()
    v.set_data(_df())
    v.edit_request = {"id": 1, "action": "set", "plate": "P1", "wells": ["A01"], "field": "Treatment", "value": "X"}
    v.set_data(_df())
    assert v.can_undo is False


def test_empty_dataframe():
    v = PlateViewer()
    v.set_data(pd.DataFrame())
    assert v.plates == [] and v.values == {} and v.current_plate == ""
