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


def render_form(form, model_cls: Type[BaseModel]):
    """Lay out a form from :func:`model_form`: scalars stacked, sub-models in accordions."""
    import marimo as mo

    scalars: List[Any] = []
    sections: Dict[str, Any] = {}
    for name, field in model_cls.model_fields.items():
        kind, sub = _field_kind(field.annotation)
        if kind == "model":
            sections[_label(name, field)] = render_form(form[name], sub)
        elif kind == "list":
            items = [
                mo.vstack([mo.md(f"**{sub.__name__} {i + 1}**"), render_form(item, sub)])
                for i, item in enumerate(form[name])
            ]
            sections[_label(name, field)] = mo.vstack(items)
        else:
            scalars.append(form[name])
    parts: List[Any] = list(scalars)
    if sections:
        parts.append(mo.accordion(sections, multiple=True))
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
