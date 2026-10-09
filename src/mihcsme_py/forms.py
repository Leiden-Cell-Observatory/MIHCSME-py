"""Build marimo forms from MIHCSME Pydantic models and read them back.

Requires marimo (``app`` extra) for :func:`model_form` and :func:`render_form`;
:func:`form_to_model` only needs pydantic.
"""

import inspect
from typing import Any, Dict, List, Optional, Tuple, Type, Union, get_args, get_origin

from pydantic import BaseModel, ValidationError

_LONG_TEXT_HINTS = ("description", "protocol", "conditions")


def _field_kind(annotation: Any) -> Tuple[str, Optional[Type[BaseModel]]]:
    """Classify a field annotation as ("scalar"|"model"|"list", sub_model)."""
    if get_origin(annotation) is Union:
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        return _field_kind(non_none[0]) if len(non_none) == 1 else ("scalar", None)
    if get_origin(annotation) in (list, List):
        inner = get_args(annotation)[0] if get_args(annotation) else None
        if inspect.isclass(inner) and issubclass(inner, BaseModel):
            return "list", inner
        return "scalar", None
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        return "model", annotation
    return "scalar", None


def _label(name: str, field: Any) -> str:
    return field.alias or name.replace("_", " ").capitalize()


def model_form(model_cls: Type[BaseModel], instance: Optional[BaseModel] = None, extra_items: int = 2):
    """Return a ``mo.ui.dictionary`` mirroring ``model_cls``, prefilled from ``instance``."""
    import marimo as mo

    elements: Dict[str, Any] = {}
    for name, field in model_cls.model_fields.items():
        current = getattr(instance, name, None) if instance is not None else None
        kind, sub = _field_kind(field.annotation)
        if kind == "model":
            elements[name] = model_form(sub, current, extra_items)
        elif kind == "list":
            items = list(current or [])
            forms = [model_form(sub, item, extra_items) for item in items]
            forms += [model_form(sub, None, extra_items) for _ in range(extra_items)]
            elements[name] = mo.ui.array(forms)
        else:
            widget = mo.ui.text_area if any(h in name for h in _LONG_TEXT_HINTS) else mo.ui.text
            elements[name] = widget(
                value="" if current is None else str(current),
                label=_label(name, field),
                placeholder=(field.description or "")[:80],
                full_width=True,
            )
    return mo.ui.dictionary(elements)


def render_form(
    form,
    model_cls: Type[BaseModel],
    suggestions: Optional[Dict[str, Any]] = None,
    prefix: str = "",
):
    """Lay out a form from :func:`model_form`: scalars stacked, sub-models in accordions.

    ``suggestions`` maps dotted field paths (see :func:`flatten_values`) to an
    element shown directly under that field, e.g. an "accept value from file" row.
    """
    import marimo as mo

    suggestions = suggestions or {}
    scalars: List[Any] = []
    sections: Dict[str, Any] = {}
    for name, field in model_cls.model_fields.items():
        kind, sub = _field_kind(field.annotation)
        path = f"{prefix}{name}"
        if kind == "model":
            sections[_label(name, field)] = render_form(form[name], sub, suggestions, f"{path}.")
        elif kind == "list":
            items = [
                mo.vstack(
                    [
                        mo.md(f"**{sub.__name__} {i + 1}**"),
                        render_form(item, sub, suggestions, f"{path}.{i}."),
                    ]
                )
                for i, item in enumerate(form[name])
            ]
            sections[_label(name, field)] = mo.vstack(items)
        else:
            scalars.append(form[name])
            if path in suggestions:
                scalars.append(suggestions[path])
    parts: List[Any] = list(scalars)
    if sections:
        # Open the first section, plus every section that has a suggestion
        with_hints = {
            _label(name, field)
            for name, field in model_cls.model_fields.items()
            if any(p.startswith(f"{prefix}{name}.") for p in suggestions)
        }
        expanded = [k for k in sections if k in with_hints] or list(sections)[:1]
        parts.append(mo.accordion(sections, multiple=True, expanded=expanded))
    return mo.vstack(parts, gap=0.5)


def _form_data(model_cls: Type[BaseModel], value: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert form values to model data; ``None`` if every field is empty."""
    data: Dict[str, Any] = {}
    for name, field in model_cls.model_fields.items():
        kind, sub = _field_kind(field.annotation)
        raw = value.get(name)
        if kind == "model":
            data[name] = _form_data(sub, raw or {})
        elif kind == "list":
            items = [_form_data(sub, item or {}) for item in (raw or [])]
            data[name] = [item for item in items if item is not None]
        else:
            text = "" if raw is None else str(raw).strip()
            data[name] = text or None
    if all(v is None or v == [] for v in data.values()):
        return None
    return data


def form_to_model(
    model_cls: Type[BaseModel], value: Dict[str, Any]
) -> Tuple[Optional[BaseModel], Optional[str]]:
    """Validate form values into ``model_cls``; return ``(model, None)`` or ``(None, error)``."""
    data = _form_data(model_cls, value) or {}
    try:
        return model_cls.model_validate(data), None
    except ValidationError as e:
        messages = [
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()
        ]
        return None, "\n".join(messages)



def model_values(
    model_cls: Type[BaseModel], instance: Optional[BaseModel] = None, extra_items: int = 0
) -> Dict[str, Any]:
    """Form-shaped values for ``instance`` (same structure as ``model_form(...).value``)."""
    values: Dict[str, Any] = {}
    for name, field in model_cls.model_fields.items():
        current = getattr(instance, name, None) if instance is not None else None
        kind, sub = _field_kind(field.annotation)
        if kind == "model":
            values[name] = model_values(sub, current, extra_items)
        elif kind == "list":
            items = [model_values(sub, item, extra_items) for item in (current or [])]
            items += [model_values(sub, None, extra_items) for _ in range(extra_items)]
            values[name] = items
        else:
            values[name] = "" if current is None else str(current)
    return values


def flatten_values(value: Any, prefix: str = "") -> Dict[str, str]:
    """Flatten nested form values to ``{"a.b": v, "items.0.c": v}``."""
    if isinstance(value, dict):
        items = value.items()
    elif isinstance(value, list):
        items = ((str(i), v) for i, v in enumerate(value))
    else:
        return {prefix: "" if value is None else str(value)}
    flat: Dict[str, str] = {}
    for key, sub in items:
        flat.update(flatten_values(sub, f"{prefix}.{key}" if prefix else str(key)))
    return flat


def suggest_values(current: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, str]:
    """Paths where ``source`` has a non-empty value that differs from ``current``."""
    mine = flatten_values(current)
    return {
        path: value.strip()
        for path, value in flatten_values(source).items()
        if value.strip() and mine.get(path, "").strip() != value.strip()
    }


def apply_values(current: Dict[str, Any], accepted: Dict[str, str]) -> Dict[str, Any]:
    """Return a copy of ``current`` with each dotted path set; lists grow as needed."""
    import copy

    out = copy.deepcopy(current)
    for path, value in accepted.items():
        keys = path.split(".")
        node: Any = out
        for key, nxt in zip(keys[:-1], keys[1:]):
            child_default: Any = [] if nxt.isdigit() else {}
            if isinstance(node, list):
                index = int(key)
                while len(node) <= index:
                    node.append({})
                if not node[index] and child_default == []:
                    node[index] = []
                node = node[index]
            else:
                node = node.setdefault(key, child_default)
        last = keys[-1]
        if isinstance(node, list):
            index = int(last)
            while len(node) <= index:
                node.append({})
            node[index] = value
        else:
            node[last] = value
    return out


_SECTIONS = {
    "investigation_information": "InvestigationInformation",
    "study_information": "StudyInformation",
    "assay_information": "AssayInformation",
}


def assemble_metadata(metadata, wells, section_values: Dict[str, Dict[str, Any]]):
    """Combine loaded metadata with edited wells and edited form sections.

    Rows with an invalid Plate/Well are left out and reported under
    ``"assay_conditions"``; a section that fails validation keeps its loaded
    value and is reported under its key. Callers should not export or upload
    while ``errors`` is non-empty.

    Returns:
        ``(metadata, errors)`` where ``errors`` maps a section key to a message.
    """
    from mihcsme_py import models
    from mihcsme_py.plate_ops import invalid_well_rows

    errors: Dict[str, str] = {}
    bad_rows = invalid_well_rows(wells)
    if bad_rows:
        shown = wells.loc[bad_rows, ["Plate", "Well"]].astype(str).to_dict("records")
        errors["assay_conditions"] = "Invalid plate/well in rows: " + ", ".join(
            f"{r['Plate']}/{r['Well']}" for r in shown
        )
        wells = wells.drop(index=bad_rows)
    updates: Dict[str, Any] = {}
    for key, value in section_values.items():
        model, error = form_to_model(getattr(models, _SECTIONS[key]), value)
        if error:
            errors[key] = error
        else:
            updates[key] = model
    result = metadata.update_conditions_from_dataframe(wells).model_copy(update=updates)
    return result, errors
