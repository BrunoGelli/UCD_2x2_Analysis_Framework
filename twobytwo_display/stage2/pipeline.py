from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, MutableMapping


@dataclass(frozen=True)
class ParamSpec:
    name: str
    default: Any
    description: str = ""


@dataclass
class StepResult:
    data: MutableMapping[str, Any] = field(default_factory=dict)


class CutStep:
    name: str = "cut_step"
    param_specs: List[ParamSpec] = []

    def __init__(self, **params: Any):
        self.params = dict(params)

    def run(self, context: MutableMapping[str, Any]) -> StepResult:
        raise NotImplementedError


class Stage2Pipeline:
    def __init__(self, steps: List[CutStep] | None = None):
        self.steps = list(steps or [])

    def run(self, initial_context: Mapping[str, Any] | None = None) -> Dict[str, Any]:
        context: Dict[str, Any] = dict(initial_context or {})
        for step in self.steps:
            result = step.run(context)
            context.update(result.data)
        return context


class CutRegistry:
    def __init__(self):
        self._constructors: Dict[str, Callable[..., CutStep]] = {}

    def register(self, name: str, constructor: Callable[..., CutStep]) -> None:
        self._constructors[name] = constructor

    def create(self, name: str, **params: Any) -> CutStep:
        if name not in self._constructors:
            raise KeyError(f"Unknown cut step '{name}'")
        return self._constructors[name](**params)

    def names(self) -> List[str]:
        return sorted(self._constructors)
