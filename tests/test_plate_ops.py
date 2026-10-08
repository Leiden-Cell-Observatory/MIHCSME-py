"""Tests for plate_ops: pure dataframe helpers behind the plate editor."""

import math

import pandas as pd
import pytest

from mihcsme_py import plate_ops


def _df():
    return pd.DataFrame(
        {
            "Plate": ["P1", "P1", "P1", "P2"],
            "Well": ["A01", "A02", "B01", "A01"],
            "Treatment": ["DMSO", "CPD1", "CPD2", "DMSO"],
            "Dose": ["0.1", "1", "10", "0.1"],
        }
    )


class TestNormalizeWell:
    def test_pads_and_uppercases(self):
        assert plate_ops.normalize_well("a1") == "A01"
        assert plate_ops.normalize_well(" B12 ") == "B12"

    def test_invalid_returns_none(self):
        assert plate_ops.normalize_well("Q01") is None
        assert plate_ops.normalize_well("") is None
        assert plate_ops.normalize_well("A") is None


class TestDetectFormat:
    def test_96(self):
        assert plate_ops.detect_format(["A01", "H12"]) == "96"

    def test_384_by_row(self):
        assert plate_ops.detect_format(["A01", "I01"]) == "384"

    def test_384_by_column(self):
        assert plate_ops.detect_format(["A13"]) == "384"

    def test_empty_defaults_to_96(self):
        assert plate_ops.detect_format([]) == "96"


class TestApplyEdit:
    def test_sets_value_on_selected_wells_only(self):
        out = plate_ops.apply_edit(_df(), "P1", ["A01", "B01"], "Treatment", "X")
        assert out["Treatment"].tolist() == ["X", "CPD1", "X", "DMSO"]

    def test_does_not_mutate_input(self):
        df = _df()
        plate_ops.apply_edit(df, "P1", ["A01"], "Treatment", "X")
        assert df["Treatment"].tolist() == ["DMSO", "CPD1", "CPD2", "DMSO"]

    def test_new_field_is_added(self):
        out = plate_ops.apply_edit(_df(), "P1", ["A01"], "CellLine", "HeLa")
        assert out.loc[0, "CellLine"] == "HeLa"
        assert out["CellLine"].isna().sum() == 3

    def test_empty_value_unsets(self):
        out = plate_ops.apply_edit(_df(), "P1", ["A01"], "Treatment", "")
        assert pd.isna(out.loc[0, "Treatment"])

    def test_unknown_wells_are_ignored(self):
        out = plate_ops.apply_edit(_df(), "P1", ["H12"], "Treatment", "X")
        assert out["Treatment"].tolist() == ["DMSO", "CPD1", "CPD2", "DMSO"]

    def test_normalises_requested_wells(self):
        out = plate_ops.apply_edit(_df(), "P1", ["a1"], "Treatment", "X")
        assert out.loc[0, "Treatment"] == "X"


class TestWidgetPayload:
    def test_shape(self):
        p = plate_ops.widget_payload(_df(), "Treatment", "96")
        assert p["plates"] == ["P1", "P2"]
        assert p["fields"] == ["Treatment", "Dose"]
        assert len(p["values"]["P1"]) == 96
        assert p["values"]["P1"][0] == "DMSO"  # A01
        assert p["values"]["P1"][1] == "CPD1"  # A02
        assert p["values"]["P1"][12] == "CPD2"  # B01
        assert p["values"]["P1"][2] is None

    def test_values_are_strings(self):
        df = _df().assign(Dose=[0.1, 1, 10, 0.1])
        p = plate_ops.widget_payload(df, "Dose", "96")
        assert p["values"]["P1"][0] == "0.1"

    def test_widget_payload_nan_becomes_none(self):
        df = _df()
        df.loc[0, "Treatment"] = float("nan")
        p = plate_ops.widget_payload(df, "Treatment", "96")
        assert p["values"]["P1"][0] is None
        assert not any(isinstance(v, float) and math.isnan(v) for v in p["values"]["P1"])

    def test_widget_payload_normalises_well_names(self):
        df = _df().assign(Well=["a1", "A2", "b1", "A1"])
        p = plate_ops.widget_payload(df, "Treatment", "96")
        assert p["values"]["P1"][0] == "DMSO"
        assert p["values"]["P1"][12] == "CPD2"

    def test_widget_payload_ignores_wells_outside_grid(self):
        df = _df().assign(Well=["A01", "A30", "Q01", "A01"])
        p = plate_ops.widget_payload(df, "Treatment", "96")
        assert len(p["values"]["P1"]) == 96
        assert p["values"]["P1"][0] == "DMSO"
        assert p["values"]["P1"].count(None) == 95

    def test_no_color_field_gives_all_none(self):
        p = plate_ops.widget_payload(_df(), None, "96")
        assert set(p["values"]["P1"]) == {None}

    def test_empty_dataframe(self):
        p = plate_ops.widget_payload(pd.DataFrame(), None, "96")
        assert p == {"plates": [], "fields": [], "values": {}}


class TestDetailPayload:
    def test_current_plate_only_and_strings(self):
        d = plate_ops.detail_payload(_df(), "P1")
        assert set(d) == {"A01", "A02", "B01"}
        assert d["A01"] == {"Treatment": "DMSO", "Dose": "0.1"}

    def test_drops_missing_values(self):
        df = _df()
        df.loc[0, "Dose"] = None
        assert plate_ops.detail_payload(df, "P1")["A01"] == {"Treatment": "DMSO"}
