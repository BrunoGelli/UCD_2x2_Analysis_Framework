from __future__ import annotations

from typing import Any, Dict, Iterable

import panel as pn

from .pipeline import ParamSpec


def widget_from_param_spec(param_spec: ParamSpec, value: Any = None):
    v = param_spec.default if value is None else value
    label = param_spec.label or param_spec.name
    kind = param_spec.kind

    if kind is None:
        if isinstance(v, bool):
            kind = "bool"
        elif isinstance(v, int) and not isinstance(v, bool):
            kind = "int"
        elif isinstance(v, float):
            kind = "float"
        else:
            kind = "str"

    if kind == "float":
        return pn.widgets.FloatInput(name=label, value=float(v), step=param_spec.step if param_spec.step is not None else 0.1)
    if kind == "int":
        return pn.widgets.IntInput(name=label, value=int(v), step=int(param_spec.step) if param_spec.step is not None else 1)
    if kind == "bool":
        return pn.widgets.Checkbox(name=label, value=bool(v))
    if kind == "select":
        return pn.widgets.Select(name=label, value=v, options=list(param_spec.options or []))
    return pn.widgets.TextInput(name=label, value=str(v))


def widgets_from_param_specs(param_specs: Iterable[ParamSpec], values: Dict[str, Any] | None = None):
    values = values or {}
    return {ps.name: widget_from_param_spec(ps, value=values.get(ps.name, None)) for ps in param_specs}
