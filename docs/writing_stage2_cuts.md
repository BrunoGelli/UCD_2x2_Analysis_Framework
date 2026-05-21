# Writing New Stage 2 Cuts, Filters, and Producers

This document explains how to add new Stage 2 analysis steps to the **UCD 2x2 Analysis Framework**.

Stage 2 is the YAML-driven tagging/cut pipeline used by both:

1. the interactive event display, and
2. the local/batch Stage 2 runner.

The core idea is:

```text
same YAML config
same ordered Stage 2 pipeline
same cut/filter/producer classes

used by:
  - event display
  - local batch runner
  - future NERSC production
  - future tag-HDF5 writer
```

A new cut should therefore be written once as a reusable Stage 2 step, then registered so it can be used from YAML, the GUI, and batch mode.

---

## 1. Where Stage 2 code lives

Current package layout:

```text
src/
└── ucd2x2/
    ├── core/
    │   ├── io.py
    │   ├── geometry.py
    │   ├── selection.py
    │   └── clustering.py
    │
    ├── display/
    │   ├── app_panel.py
    │   └── viz.py
    │
    └── stage2/
        ├── __init__.py
        ├── config.py
        ├── masking.py
        ├── pipeline.py
        ├── pipeline_ui.py
        ├── run_stage2.py
        ├── widgets.py
        └── cuts/
            ├── __init__.py
            ├── repeated_pixel_filter.py
            └── dbscan_cluster_producer.py
```

New Stage 2 cut/filter/producer scripts should usually go in:

```text
src/ucd2x2/stage2/cuts/
```

For example:

```text
src/ucd2x2/stage2/cuts/muon_cylinder_filter.py
src/ucd2x2/stage2/cuts/ransac_muon_line_producer.py
src/ucd2x2/stage2/cuts/charge_threshold_filter.py
```

---

## 2. The Stage 2 mental model

Stage 2 is an ordered pipeline.

A YAML config like:

```yaml
pipeline:
  - name: repeated_pixel_filter
    enabled: true
    params:
      max_hits_per_pixel: 10
      pixel_fields: "y,z"
      round_decimals: 3

  - name: dbscan_cluster_producer
    enabled: true
    params:
      eps_cm: 1.5
      min_samples: 10
      cluster_min_hits: 20
      cluster_max_extent_cm: 8.0
```

means:

```text
1. Build RepeatedPixelFilter(max_hits_per_pixel=10, pixel_fields="y,z", round_decimals=3)
2. Run it on the event context.
3. Update the context with its outputs.
4. Build DBSCANClusterProducer(eps_cm=1.5, ...)
5. Run it on the updated context.
6. Update the context with its outputs.
```

The order matters.

For example:

```text
repeated_pixel_filter -> dbscan_cluster_producer
```

is different from:

```text
dbscan_cluster_producer -> repeated_pixel_filter
```

because DBSCAN respects the `active_mask` produced by earlier filters.

---

## 3. Main Stage 2 classes

The important classes live in:

```python
from ucd2x2.stage2.pipeline import CutStep, ParamSpec, StepResult, Stage2Pipeline
```

### 3.1 `CutStep`

Every Stage 2 step should inherit from `CutStep`.

A step must define:

```python
class MyStep(CutStep):
    name = "my_step_name"
    param_specs = [...]

    def run(self, context):
        ...
        return StepResult({...})
```

The `name` is the string used in YAML.

For example:

```yaml
pipeline:
  - name: my_step_name
    enabled: true
    params:
      ...
```

### 3.2 `ParamSpec`

`ParamSpec` describes a user-facing parameter.

It is used by the event display to create widgets automatically, and by humans to understand what the YAML parameters mean.

Example:

```python
ParamSpec(
    "max_hits_per_pixel",
    10,
    "Deactivate pixels above this occupancy",
    label="Max hits per pixel",
    kind="int",
    step=1,
)
```

Current useful fields:

```python
ParamSpec(
    name,             # parameter name used in params/YAML
    default,          # default value
    description="",   # human-readable description
    label=None,       # widget label; falls back to name
    kind=None,        # "int", "float", "bool", "str", or "select"
    min_value=None,   # optional future bounds
    max_value=None,   # optional future bounds
    step=None,        # widget step size
    options=None,     # for select widgets
)
```

The event display uses this metadata to make widgets.

So if you define good `ParamSpec`s, your cut becomes automatically editable in the Stage 2 pipeline editor.

### 3.3 `StepResult`

A step returns a `StepResult`.

Example:

```python
return StepResult({
    "active_mask": active_mask,
    "n_removed_hits": int(np.sum(removed_mask)),
})
```

The pipeline then updates the shared event context with this data.

So:

```python
context.update(result.data)
```

happens after each step.

### 3.4 `Stage2Pipeline`

The pipeline runs steps in order.

Conceptually:

```python
context = {"hits": hits, "event_index": event_index, ...}

for step in steps:
    result = step.run(context)
    context.update(result.data)

return context
```

This is why step names and output keys matter. Later steps see the outputs from earlier steps.

---

## 4. The event context

Every Stage 2 step receives a `context` dictionary.

Common keys include:

```text
hits
  Structured NumPy array of event hits.

event_index
  Integer event index in the input file.

event_id
  Event ID if available from the file.

muon_track
  Rock-muon track object if available/selected, otherwise None.

active_mask
  Boolean mask of currently active hits.
  If absent, all hits should be treated as active.
```

The most important key is usually:

```python
hits = context.get("hits")
```

The `hits` object is normally a structured NumPy array with fields such as:

```text
x
y
z
Q
t_drift
ts_pps
...
```

Do not assume every field exists unless your step explicitly requires it. If your cut requires a field, check for it and raise a clear error.

Example:

```python
if "Q" not in hits.dtype.names:
    raise ValueError("charge_threshold_filter requires hit field 'Q'")
```

---

## 5. The `active_mask` convention

The `active_mask` is the current in-memory selection mask for hits.

It should have the same length as `hits`.

```text
active_mask[i] == True
  hit i is still active

active_mask[i] == False
  hit i has been removed/masked by an earlier filter
```

Use:

```python
from ucd2x2.stage2.masking import get_active_mask
```

Example:

```python
active_mask = get_active_mask(context, len(hits)).copy()
```

`get_active_mask` does two things:

1. If `context["active_mask"]` exists, it returns it as a boolean array.
2. If it does not exist, it returns an all-True mask.

It also checks that the mask length matches `len(hits)`.

### Filters should update `active_mask`

A filter should normally do:

```python
active_mask = get_active_mask(context, len(hits)).copy()
removed_mask = ...
active_mask[removed_mask] = False

return StepResult({
    "active_mask": active_mask,
    "my_filter_removed_mask": removed_mask,
    "n_my_filter_removed_hits": int(np.sum(removed_mask)),
})
```

### Producers should respect `active_mask`

A producer should not usually modify `active_mask`.

Instead, it should use the existing `active_mask` to decide which hits to process.

Example:

```python
active_mask = get_active_mask(context, len(hits))
clusters = make_clusters(hits[active_mask])
```

The current `DBSCANClusterProducer` does this: it combines the existing `active_mask` with its own muon-region mask before clustering.

---

## 6. Types of Stage 2 steps

Stage 2 steps can be thought of as three rough categories.

These categories are conceptual; the code currently uses `CutStep` for all of them.

### 6.1 Filter

A filter removes or masks hits from downstream processing.

Example:

```text
RepeatedPixelFilter
ChargeThresholdFilter
MuonCylinderFilter
FiducialVolumeFilter
```

Typical output:

```python
StepResult({
    "active_mask": active_mask,
    "some_removed_mask": removed_mask,
    "n_some_removed_hits": n_removed,
})
```

### 6.2 Tagger

A tagger labels hits or events but may not remove anything.

Example:

```text
HotRegionTagger
LowChargeTagger
NearMuonTagger
```

Typical output:

```python
StepResult({
    "near_muon_mask": near_muon_mask,
    "n_near_muon_hits": int(np.sum(near_muon_mask)),
})
```

A tagger may or may not update `active_mask`.

### 6.3 Producer

A producer creates higher-level objects.

Example:

```text
DBSCANClusterProducer
RANSACMuonLineProducer
BlipCandidateProducer
```

Typical output:

```python
StepResult({
    "clusters": clusters,
})
```

or:

```python
StepResult({
    "ransac_muon_line": line,
    "ransac_inlier_mask": inlier_mask,
})
```

---

## 7. How YAML connects to the cut script

The YAML only stores:

```text
step name
enabled flag
parameter values
order
```

Example:

```yaml
pipeline:
  - name: repeated_pixel_filter
    enabled: true
    params:
      max_hits_per_pixel: 10
      pixel_fields: "y,z"
      round_decimals: 3
```

This does not directly import Python code.

Instead, the connection happens through the Stage 2 registry.

The default registry lives in:

```text
src/ucd2x2/stage2/config.py
```

and looks conceptually like:

```python
def default_registry() -> CutRegistry:
    reg = CutRegistry()
    reg.register(RepeatedPixelFilter.name, RepeatedPixelFilter)
    reg.register(DBSCANClusterProducer.name, DBSCANClusterProducer)
    return reg
```

So when the YAML says:

```yaml
name: repeated_pixel_filter
```

the framework looks up:

```python
registry.create("repeated_pixel_filter", **params)
```

which becomes:

```python
RepeatedPixelFilter(max_hits_per_pixel=10, pixel_fields="y,z", round_decimals=3)
```

Therefore, adding a new cut requires two things:

1. write the class, and
2. register it.

---

## 8. How to add a new cut: checklist

To add a new Stage 2 step:

```text
1. Create a new file in src/ucd2x2/stage2/cuts/.
2. Define a class inheriting CutStep.
3. Give it a unique name string.
4. Define param_specs.
5. Implement run(context).
6. Return StepResult.
7. Export it in src/ucd2x2/stage2/cuts/__init__.py.
8. Register it in default_registry() in src/ucd2x2/stage2/config.py.
9. Add a YAML example under configs/stage2/.
10. Add tests.
11. Run pytest.
12. Try it in the event display.
13. Try it with ucd2x2 stage2-run.
```

---

## 9. Minimal filter example

Suppose we want a filter that removes hits below a charge threshold.

Create:

```text
src/ucd2x2/stage2/cuts/charge_threshold_filter.py
```

Example implementation:

```python
from __future__ import annotations

from typing import Any, MutableMapping

import numpy as np

from ucd2x2.stage2.masking import get_active_mask
from ucd2x2.stage2.pipeline import CutStep, ParamSpec, StepResult


class ChargeThresholdFilter(CutStep):
    name = "charge_threshold_filter"

    param_specs = [
        ParamSpec(
            "min_charge",
            0.0,
            "Deactivate hits with Q below this threshold",
            label="Minimum charge",
            kind="float",
            step=0.1,
        ),
        ParamSpec(
            "charge_field",
            "Q",
            "Hit field containing charge",
            label="Charge field",
            kind="str",
        ),
    ]

    def run(self, context: MutableMapping[str, Any]) -> StepResult:
        hits = context.get("hits")

        if hits is None or len(hits) == 0:
            return StepResult({
                "active_mask": np.zeros(0, dtype=bool),
                "charge_threshold_removed_mask": np.zeros(0, dtype=bool),
                "n_charge_threshold_removed_hits": 0,
            })

        field = str(self.params.get("charge_field", "Q"))

        if field not in (hits.dtype.names or ()):
            raise ValueError(f"charge_threshold_filter requires hit field '{field}'")

        active_mask = get_active_mask(context, len(hits)).copy()

        min_charge = float(self.params.get("min_charge", 0.0))
        charge = hits[field].astype(float)

        removed_mask = active_mask & (charge < min_charge)

        active_mask[removed_mask] = False

        return StepResult({
            "active_mask": active_mask,
            "charge_threshold_removed_mask": removed_mask,
            "n_charge_threshold_removed_hits": int(np.sum(removed_mask)),
        })
```

Important details:

```text
- The class inherits from CutStep.
- The name string is what YAML uses.
- param_specs controls GUI widget generation.
- The filter respects the existing active_mask.
- The filter updates active_mask.
- The filter returns diagnostic masks/counts.
```

---

## 10. Registering the new cut

Edit:

```text
src/ucd2x2/stage2/cuts/__init__.py
```

Add:

```python
from .charge_threshold_filter import ChargeThresholdFilter

__all__ = [
    "DBSCANClusterProducer",
    "RepeatedPixelFilter",
    "ChargeThresholdFilter",
]
```

Then edit:

```text
src/ucd2x2/stage2/config.py
```

Import it:

```python
from .cuts import DBSCANClusterProducer, RepeatedPixelFilter, ChargeThresholdFilter
```

Register it:

```python
def default_registry() -> CutRegistry:
    reg = CutRegistry()
    reg.register(RepeatedPixelFilter.name, RepeatedPixelFilter)
    reg.register(ChargeThresholdFilter.name, ChargeThresholdFilter)
    reg.register(DBSCANClusterProducer.name, DBSCANClusterProducer)
    return reg
```

The order in the registry does not control execution order. YAML controls execution order.

---

## 11. Add a YAML config

Create:

```text
configs/stage2/charge_then_dbscan.yaml
```

Example:

```yaml
pipeline:
  - name: charge_threshold_filter
    enabled: true
    params:
      min_charge: 0.5
      charge_field: "Q"

  - name: dbscan_cluster_producer
    enabled: true
    params:
      eps_cm: 1.5
      min_samples: 10
      cluster_min_hits: 20
      cluster_max_extent_cm: 8.0
```

This means:

```text
1. Remove hits with Q < 0.5.
2. Run DBSCAN on the remaining active hits.
```

You can load this YAML in the event display, or run it in batch.

---

## 12. Run from the event display

Launch:

```bash
ucd2x2 event-display tests/sample_data.hdf5
```

or, without the CLI:

```bash
panel serve src/ucd2x2/display/app_panel.py --show --args --h5 tests/sample_data.hdf5
```

Then in the Stage 2 pipeline editor:

1. Load your YAML config.
2. Check that your new step appears.
3. Adjust parameters.
4. Enable/disable it.
5. Move it up/down relative to other steps.
6. Save the YAML.
7. Verify the event display updates as expected.

Because the widgets are generated from `ParamSpec`, you should not need to edit `app_panel.py` just to expose a new cut.

---

## 13. Run in batch

Run:

```bash
ucd2x2 stage2-run \
  --input tests/sample_data.hdf5 \
  --config configs/stage2/charge_then_dbscan.yaml \
  --output outputs/stage2/charge_then_dbscan_summary.json
```

or, without the CLI:

```bash
python -m ucd2x2.stage2.run_stage2 \
  --input tests/sample_data.hdf5 \
  --config configs/stage2/charge_then_dbscan.yaml \
  --output outputs/stage2/charge_then_dbscan_summary.json
```

The batch runner loads the same YAML config as the event display.

That is the central design principle.

---

## 14. Add tests

Add a test file such as:

```text
tests/test_stage2_charge_threshold_filter.py
```

Example tests:

```python
import numpy as np
import pytest

from ucd2x2.stage2.cuts import ChargeThresholdFilter
from ucd2x2.stage2.config import default_registry, load_pipeline_config, pipeline_from_dict


def _hits():
    dtype = [("x", "f4"), ("y", "f4"), ("z", "f4"), ("Q", "f4")]
    h = np.zeros(5, dtype=dtype)
    h["Q"] = [0.1, 0.2, 1.0, 2.0, 3.0]
    return h


def test_charge_threshold_filter_masks_low_charge_hits():
    hits = _hits()
    step = ChargeThresholdFilter(min_charge=1.0)
    out = step.run({"hits": hits}).data

    assert out["n_charge_threshold_removed_hits"] == 2
    assert out["active_mask"].tolist() == [False, False, True, True, True]


def test_charge_threshold_filter_respects_existing_active_mask():
    hits = _hits()
    active_mask = np.array([True, False, True, True, True])
    step = ChargeThresholdFilter(min_charge=1.0)

    out = step.run({"hits": hits, "active_mask": active_mask}).data

    # Hit 1 was already inactive. Hit 0 is newly removed.
    assert out["active_mask"].tolist() == [False, False, True, True, True]


def test_charge_threshold_filter_missing_field_raises():
    hits = _hits()
    step = ChargeThresholdFilter(charge_field="missing")

    with pytest.raises(ValueError, match="requires hit field"):
        step.run({"hits": hits})


def test_default_registry_includes_charge_threshold_filter():
    reg = default_registry()
    step = reg.create("charge_threshold_filter", min_charge=1.0)
    assert isinstance(step, ChargeThresholdFilter)


def test_charge_threshold_yaml_loads():
    cfg = load_pipeline_config("configs/stage2/charge_then_dbscan.yaml")
    pipeline = pipeline_from_dict(cfg, registry=default_registry())
    assert len(pipeline.steps) == 2
```

Then run:

```bash
pytest -q
```

---

## 15. Naming conventions

Use clear names.

Good step names:

```text
repeated_pixel_filter
charge_threshold_filter
fiducial_volume_filter
ransac_muon_line_producer
muon_cylinder_filter
dbscan_cluster_producer
```

Avoid vague names:

```text
cut1
my_filter
test_cut
new_dbscan
```

Recommended suffixes:

```text
*_filter
  modifies active_mask

*_tagger
  creates masks/tags but does not necessarily modify active_mask

*_producer
  creates objects such as clusters, lines, candidates
```

---

## 16. Output key conventions

Use explicit output names.

Good:

```python
"active_mask"
"repeated_pixel_mask"
"n_repeated_pixel_hits"
"n_repeated_pixels"
"charge_threshold_removed_mask"
"n_charge_threshold_removed_hits"
"clusters"
"ransac_muon_line"
"ransac_inlier_mask"
```

Avoid:

```python
"mask"
"count"
"result"
"data"
```

Why?

Because all steps share one context dictionary. Ambiguous names can overwrite each other.

---

## 17. A note on masks and future tag HDF5

Right now, Stage 2 masks are in-memory during event display and batch execution.

Eventually, Stage 2 will write a tag HDF5 file. At that point, masks and tag outputs like:

```text
repeated_pixel_mask
charge_threshold_removed_mask
active_mask
```

can become persistent packet/hit tags.

That is why it is important to return named masks and counts now, even if we are not writing them to HDF5 yet.

Good current behavior:

```python
return StepResult({
    "active_mask": active_mask,
    "my_cut_removed_mask": removed_mask,
    "n_my_cut_removed_hits": int(np.sum(removed_mask)),
})
```

Future behavior:

```text
same outputs can be written to tag HDF5
same YAML config
same provenance
same batch/display logic
```

---

## 18. How the event display sees a new cut

The event display uses the registry and `ParamSpec` metadata.

So once your step is:

1. implemented,
2. exported from `cuts/__init__.py`,
3. registered in `default_registry()`,

then the generic Stage 2 pipeline editor can:

```text
- show it in the "Add step" dropdown
- create widgets from param_specs
- load it from YAML
- save it back to YAML
- run it before/after other steps
```

That is the point of the architecture.

You should not need to manually add new widgets to `app_panel.py` for every new cut.

---

## 19. Common pitfalls

### Pitfall 1: Forgetting to register the step

Symptom:

```text
Unknown stage2 step 'my_new_filter'
```

Fix:

```python
reg.register(MyNewFilter.name, MyNewFilter)
```

inside `default_registry()`.

---

### Pitfall 2: Updating `active_mask` in place without copying

Avoid:

```python
active_mask = get_active_mask(context, len(hits))
active_mask[removed_mask] = False
```

Prefer:

```python
active_mask = get_active_mask(context, len(hits)).copy()
active_mask[removed_mask] = False
```

Copying avoids surprising side effects.

---

### Pitfall 3: Ignoring existing `active_mask`

Bad:

```python
active_mask = np.ones(len(hits), dtype=bool)
```

Good:

```python
active_mask = get_active_mask(context, len(hits)).copy()
```

This lets your cut respect earlier cuts.

---

### Pitfall 4: Using generic output names

Bad:

```python
return StepResult({"mask": mask})
```

Good:

```python
return StepResult({"charge_threshold_removed_mask": mask})
```

---

### Pitfall 5: Hardcoding GUI behavior

Do not add custom widgets to `app_panel.py` unless absolutely necessary.

Prefer:

```python
param_specs = [...]
```

The generic UI should handle the rest.

---

### Pitfall 6: Assuming all files have all fields

Check required hit fields explicitly.

Example:

```python
if "Q" not in hits.dtype.names:
    raise ValueError("charge_threshold_filter requires hit field 'Q'")
```

---

## 20. Recommended development workflow

For a new cut:

```bash
git checkout -b add-charge-threshold-filter
```

Then:

```text
1. Add the cut script.
2. Register it.
3. Add YAML example.
4. Add tests.
5. Run pytest.
6. Test in the event display.
7. Test with stage2-run.
8. Open PR.
```

Commands:

```bash
pip install -e .
pytest -q
python -c "import ucd2x2.display.app_panel"
```

Interactive check:

```bash
ucd2x2 event-display tests/sample_data.hdf5
```

Batch check:

```bash
ucd2x2 stage2-run \
  --input tests/sample_data.hdf5 \
  --config configs/stage2/charge_then_dbscan.yaml \
  --output /tmp/stage2_summary.json
```

---

## 21. Minimal new-cut template

Copy this when starting a new filter:

```python
from __future__ import annotations

from typing import Any, MutableMapping

import numpy as np

from ucd2x2.stage2.masking import get_active_mask
from ucd2x2.stage2.pipeline import CutStep, ParamSpec, StepResult


class MyNewFilter(CutStep):
    name = "my_new_filter"

    param_specs = [
        ParamSpec(
            "my_parameter",
            1.0,
            "Description of my parameter",
            label="My parameter",
            kind="float",
            step=0.1,
        ),
    ]

    def run(self, context: MutableMapping[str, Any]) -> StepResult:
        hits = context.get("hits")

        if hits is None or len(hits) == 0:
            return StepResult({
                "active_mask": np.zeros(0, dtype=bool),
                "my_new_filter_removed_mask": np.zeros(0, dtype=bool),
                "n_my_new_filter_removed_hits": 0,
            })

        active_mask = get_active_mask(context, len(hits)).copy()

        # Implement your logic here.
        removed_mask = np.zeros(len(hits), dtype=bool)

        # Example:
        # removed_mask = active_mask & some_condition

        active_mask[removed_mask] = False

        return StepResult({
            "active_mask": active_mask,
            "my_new_filter_removed_mask": removed_mask,
            "n_my_new_filter_removed_hits": int(np.sum(removed_mask)),
        })
```

Then register it and add tests.

---

## 22. Summary

A new Stage 2 cut hooks into the YAML-based structure through this chain:

```text
Python class inheriting CutStep
        |
        v
unique class.name string
        |
        v
registered in default_registry()
        |
        v
referenced by YAML pipeline step name
        |
        v
instantiated with YAML params
        |
        v
shown in event display using ParamSpec widgets
        |
        v
run in event display and batch using same Stage2Pipeline
```

That is the key architecture.

Write the cut once. Register it once. Then use it everywhere.
