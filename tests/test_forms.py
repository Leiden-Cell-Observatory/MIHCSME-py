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
