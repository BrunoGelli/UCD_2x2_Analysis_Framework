from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping

from .config import default_registry
from .widgets import widgets_from_param_specs


@dataclass
class UIStepState:
    name: str
    enabled: bool
    params: Dict[str, Any]


def config_to_ui_steps(config: Mapping[str, Any], registry=None) -> List[UIStepState]:
    registry = registry or default_registry()
    names = set(registry.names())
    out: List[UIStepState] = []
    for i, step in enumerate(config.get("pipeline", [])):
        if not isinstance(step, Mapping):
            raise ValueError(f"Invalid step at index {i}")
        name = step.get("name")
        if name not in names:
            raise ValueError(f"Unknown stage2 step '{name}'")
        out.append(UIStepState(name=name, enabled=bool(step.get("enabled", True)), params=dict(step.get("params", {}))))
    return out


def ui_steps_to_config(steps: List[UIStepState]) -> Dict[str, Any]:
    return {"pipeline": [{"name": s.name, "enabled": bool(s.enabled), "params": dict(s.params)} for s in steps]}


def add_step(steps: List[UIStepState], name: str, registry=None) -> List[UIStepState]:
    registry = registry or default_registry()
    step = registry.create(name)
    defaults = {ps.name: ps.default for ps in step.param_specs}
    return [*steps, UIStepState(name=name, enabled=True, params=defaults)]


def remove_step(steps: List[UIStepState], index: int) -> List[UIStepState]:
    return [s for i, s in enumerate(steps) if i != index]


def move_step(steps: List[UIStepState], index: int, direction: int) -> List[UIStepState]:
    j = index + direction
    if j < 0 or j >= len(steps):
        return steps
    new = list(steps)
    new[index], new[j] = new[j], new[index]
    return new


def widgets_for_step(name: str, values: Dict[str, Any] | None = None, registry=None):
    registry = registry or default_registry()
    step = registry.create(name)
    return widgets_from_param_specs(step.param_specs, values=values or {})
