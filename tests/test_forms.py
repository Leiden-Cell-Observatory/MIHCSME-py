"""Tests for generated Pydantic <-> marimo forms."""

import pytest

pytest.importorskip("marimo")

from mihcsme_py.forms import form_to_model, model_form  # noqa: E402
from mihcsme_py.models import (  # noqa: E402
    AssayInformation,
    Channel,
    DataCollaborator,
    DataOwner,
    InvestigationInformation,
    Specimen,
)


def test_form_prefills_scalar_and_nested_values():
    inv = InvestigationInformation(
        data_owner=DataOwner(first_name="Ada", last_name="Lovelace"),
        data_collaborators=[DataCollaborator(orcid="https://orcid.org/0000-0000-0000-0001")],
    )
    form = model_form(InvestigationInformation, inv)
    value = form.value
    assert value["data_owner"]["first_name"] == "Ada"
    assert value["data_owner"]["email"] == ""
    assert value["data_collaborators"][0]["orcid"] == "https://orcid.org/0000-0000-0000-0001"
    assert len(value["data_collaborators"]) == 3  # 1 existing + 2 blank


def test_form_without_instance_is_blank():
    value = model_form(InvestigationInformation).value
    assert value["data_owner"]["first_name"] == ""
    assert len(value["data_collaborators"]) == 2


def test_round_trip_unchanged():
    inv = InvestigationInformation(data_owner=DataOwner(first_name="Ada"))
    model, error = form_to_model(InvestigationInformation, model_form(InvestigationInformation, inv).value)
    assert error is None
    assert model.data_owner.first_name == "Ada"
    assert model.data_owner.email is None
    assert model.data_collaborators == []


def test_blank_list_items_are_dropped_and_nested_lists_work():
    spec = Specimen(channels=[Channel(entity="DNA", label="Nuclei", id="1")])
    info = AssayInformation(specimen=spec)
    model, error = form_to_model(AssayInformation, model_form(AssayInformation, info).value)
    assert error is None
    assert [c.entity for c in model.specimen.channels] == ["DNA"]


def test_whitespace_becomes_none():
    value = model_form(InvestigationInformation).value
    value["data_owner"]["first_name"] = "   "
    model, error = form_to_model(InvestigationInformation, value)
    assert error is None
    assert model.data_owner is None  # all-empty sub-model collapses to None


def test_form_to_model_returns_error_for_bad_orcid():
    value = model_form(InvestigationInformation).value
    value["data_owner"]["orcid"] = "0000-0001"
    model, error = form_to_model(InvestigationInformation, value)
    assert model is None
    assert "data_owner.orcid" in error


def _metadata():
    import pandas as pd
    from mihcsme_py.models import MIHCSMEMetadata

    wells = pd.DataFrame({"Plate": ["P1", "P1"], "Well": ["A01", "A02"], "Treatment": ["DMSO", "X"]})
    inv = InvestigationInformation(data_owner=DataOwner(first_name="Ada"))
    return MIHCSMEMetadata.from_dataframe(wells, investigation_information=inv), wells


def test_assemble_metadata_applies_wells_and_sections():
    from mihcsme_py.forms import assemble_metadata

    metadata, wells = _metadata()
    values = model_form(InvestigationInformation, metadata.investigation_information).value
    values["data_owner"]["first_name"] = "Grace"
    result, errors = assemble_metadata(metadata, wells, {"investigation_information": values})
    assert errors == {}
    assert result.investigation_information.data_owner.first_name == "Grace"
    assert len(result.assay_conditions) == 2


def test_assemble_metadata_reports_bad_section_and_bad_wells():
    from mihcsme_py.forms import assemble_metadata

    metadata, wells = _metadata()
    wells = wells.assign(Well=["A01", "Q01"])
    values = model_form(InvestigationInformation, metadata.investigation_information).value
    values["data_owner"]["orcid"] = "not-an-orcid"
    result, errors = assemble_metadata(metadata, wells, {"investigation_information": values})
    assert set(errors) == {"investigation_information", "assay_conditions"}
    assert "Q01" in errors["assay_conditions"]
    assert [c.well for c in result.assay_conditions] == ["A01"]


class TestSuggestions:
    def test_model_values_matches_form_value(self):
        from mihcsme_py.forms import model_values

        inv = InvestigationInformation(
            data_owner=DataOwner(first_name="Ada"),
            data_collaborators=[DataCollaborator(orcid="https://orcid.org/0000-0000-0000-0001")],
        )
        assert model_values(InvestigationInformation, inv, extra_items=2) == model_form(
            InvestigationInformation, inv
        ).value

    def test_flatten_values_uses_dotted_paths(self):
        from mihcsme_py.forms import flatten_values

        flat = flatten_values({"a": {"b": "x"}, "items": [{"c": "y"}], "d": ""})
        assert flat == {"a.b": "x", "items.0.c": "y", "d": ""}

    def test_suggest_values_only_non_empty_and_different(self):
        from mihcsme_py.forms import suggest_values

        current = {"data_owner": {"first_name": "Ada", "last_name": "", "email": "a@b.c"}}
        source = {"data_owner": {"first_name": "Grace", "last_name": "Hopper", "email": ""}}
        assert suggest_values(current, source) == {
            "data_owner.first_name": "Grace",
            "data_owner.last_name": "Hopper",
        }

    def test_suggest_values_ignores_whitespace_differences(self):
        from mihcsme_py.forms import suggest_values

        assert suggest_values({"a": "x "}, {"a": " x"}) == {}

    def test_suggest_values_includes_extra_list_items(self):
        from mihcsme_py.forms import suggest_values

        current = {"channels": [{"entity": "DNA"}]}
        source = {"channels": [{"entity": "DNA"}, {"entity": "Actin"}]}
        assert suggest_values(current, source) == {"channels.1.entity": "Actin"}

    def test_apply_values_sets_paths_and_extends_lists(self):
        from mihcsme_py.forms import apply_values

        current = {"data_owner": {"first_name": "Ada"}, "channels": [{"entity": "DNA"}]}
        out = apply_values(current, {"data_owner.first_name": "Grace", "channels.2.entity": "Actin"})
        assert out["data_owner"]["first_name"] == "Grace"
        assert out["channels"][2] == {"entity": "Actin"}
        assert out["channels"][1] == {}
        assert current["data_owner"]["first_name"] == "Ada"  # input untouched

    def test_accepted_values_round_trip_to_model(self):
        from mihcsme_py.forms import apply_values, model_values, suggest_values

        mine = InvestigationInformation(data_owner=DataOwner(first_name="Ada"))
        theirs = InvestigationInformation(
            data_owner=DataOwner(first_name="Grace", last_name="Hopper"),
            data_collaborators=[DataCollaborator(orcid="https://orcid.org/0000-0000-0000-0002")],
        )
        current = model_values(InvestigationInformation, mine)
        suggestions = suggest_values(current, model_values(InvestigationInformation, theirs))
        accepted = {k: v for k, v in suggestions.items() if k != "data_owner.first_name"}
        model, error = form_to_model(InvestigationInformation, apply_values(current, accepted))
        assert error is None
        assert model.data_owner.first_name == "Ada"
        assert model.data_owner.last_name == "Hopper"
        assert model.data_collaborators[0].orcid == "https://orcid.org/0000-0000-0000-0002"


def test_render_form_places_suggestion_under_matching_field():
    import marimo as mo

    from mihcsme_py.forms import render_form

    form = model_form(InvestigationInformation)
    html = render_form(
        form,
        InvestigationInformation,
        suggestions={
            "data_owner.last_name": mo.md("SUGGEST-LAST"),
            "data_collaborators.1.orcid": mo.md("SUGGEST-ORCID"),
        },
    ).text
    assert "SUGGEST-LAST" in html and "SUGGEST-ORCID" in html
    assert html.index("SUGGEST-LAST") > html.index("Last Name")
