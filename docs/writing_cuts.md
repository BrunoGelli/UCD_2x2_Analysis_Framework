# Writing new Stage 2 cuts/filters/producers

Use this checklist to add a new step while preserving current framework conventions.

## 1) Create a class inheriting `CutStep`

Define:
- `name` (stable registry/config identifier)
- `param_specs` (list of `ParamSpec`)
- `run(context)` implementation returning `StepResult`

### Minimal skeleton

```python
from __future__ import annotations

from typing import Any, MutableMapping

from ucd2x2.stage2.pipeline import CutStep, ParamSpec, StepResult
from ucd2x2.stage2.masking import get_active_mask


class ExampleStep(CutStep):
    name = "example_step"
    param_specs = [
        ParamSpec("threshold", 1.0, "Example threshold", kind="float"),
    ]

    def run(self, context: MutableMapping[str, Any]) -> StepResult:
        hits = context.get("hits")
        if hits is None:
            return StepResult({})

        active_mask = get_active_mask(context, len(hits)).copy()

        # ...custom logic here...

        return StepResult({
            "active_mask": active_mask,
            "example_metric": 0,
        })
```

## 2) Update `active_mask` if this is a filter

If your step is filtering hits, do not delete rows; update and return `active_mask`.

## 3) Register the step in `default_registry`

Add registration in `src/ucd2x2/stage2/config.py` so YAML and UI can resolve the step name.

## 4) Add config example(s)

Add or update YAML under `configs/stage2/` showing the new step in realistic order.

## 5) Add tests

At minimum, cover:
- step behavior on representative fixture data,
- config load/validation path,
- pipeline integration expectations.

## 6) Keep behavior composable

Prefer emitting context fields that can be consumed by later steps without hidden side effects.
