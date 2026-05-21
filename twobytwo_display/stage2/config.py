from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping

import yaml

from .cuts import DBSCANClusterProducer
from .pipeline import CutRegistry, Stage2Pipeline


@dataclass(frozen=True)
class PipelineStepConfig:
    name: str
    enabled: bool
    params: Dict[str, Any]


def default_registry() -> CutRegistry:
    reg = CutRegistry()
    reg.register(DBSCANClusterProducer.name, DBSCANClusterProducer)
    return reg


def _validate_config_dict(config: Mapping[str, Any]) -> List[PipelineStepConfig]:
    if not isinstance(config, Mapping):
        raise ValueError("Stage2 config must be a mapping with key 'pipeline'")
    raw_steps = config.get("pipeline")
    if not isinstance(raw_steps, list):
        raise ValueError("Stage2 config 'pipeline' must be a list")

    out: List[PipelineStepConfig] = []
    for i, item in enumerate(raw_steps):
        if not isinstance(item, Mapping):
            raise ValueError(f"Stage2 config step at index {i} must be a mapping")
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"Stage2 config step at index {i} requires non-empty string 'name'")
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"Stage2 config step '{name}' has non-boolean 'enabled'")
        params = item.get("params", {})
        if not isinstance(params, Mapping):
            raise ValueError(f"Stage2 config step '{name}' has non-mapping 'params'")
        out.append(PipelineStepConfig(name=name, enabled=enabled, params=dict(params)))
    return out


def pipeline_from_dict(config: Mapping[str, Any], registry: CutRegistry | None = None) -> Stage2Pipeline:
    registry = registry or default_registry()
    step_cfgs = _validate_config_dict(config)
    steps = []
    for step_cfg in step_cfgs:
        if not step_cfg.enabled:
            continue
        try:
            steps.append(registry.create(step_cfg.name, **step_cfg.params))
        except KeyError as e:
            raise ValueError(f"Unknown stage2 step '{step_cfg.name}'. Registered steps: {registry.names()}") from e
    return Stage2Pipeline(steps)


def pipeline_to_dict(config: Mapping[str, Any]) -> Dict[str, Any]:
    steps = _validate_config_dict(config)
    return {
        "pipeline": [
            {"name": s.name, "enabled": s.enabled, "params": dict(s.params)}
            for s in steps
        ]
    }


def load_pipeline_config(path: str | Path) -> Dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text())
    return pipeline_to_dict(data)


def load_pipeline(path: str | Path, registry: CutRegistry | None = None) -> Stage2Pipeline:
    return pipeline_from_dict(load_pipeline_config(path), registry=registry)


def dump_pipeline_config(config: Mapping[str, Any]) -> str:
    normalized = pipeline_to_dict(config)
    return yaml.safe_dump(normalized, sort_keys=False)
