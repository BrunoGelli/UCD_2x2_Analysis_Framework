from .pipeline import ParamSpec, StepResult, CutStep, Stage2Pipeline, CutRegistry
from .config import (
    PipelineStepConfig,
    default_registry,
    pipeline_from_dict,
    pipeline_to_dict,
    load_pipeline_config,
    load_pipeline,
    dump_pipeline_config,
)


def run_stage2_file(*args, **kwargs):
    """Lazy import wrapper to avoid runpy warning for `python -m ...run_stage2`."""
    from .run_stage2 import run_stage2_file as _run_stage2_file

    return _run_stage2_file(*args, **kwargs)

__all__ = [
    "ParamSpec",
    "StepResult",
    "CutStep",
    "Stage2Pipeline",
    "CutRegistry",
    "PipelineStepConfig",
    "default_registry",
    "pipeline_from_dict",
    "pipeline_to_dict",
    "load_pipeline_config",
    "load_pipeline",
    "dump_pipeline_config",
    "run_stage2_file",
]
