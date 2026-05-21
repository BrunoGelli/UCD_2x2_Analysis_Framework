# Stage 2 pipeline concepts

## Core abstractions

### `CutStep`

Base class for a pipeline step. A step has:
- a unique `name`,
- `param_specs` metadata for UI/config exposure,
- a `run(context)` method.

### `StepResult`

Return type from each step. It carries a mutable mapping (`data`) of context updates. Pipeline execution merges each step result into the shared context.

### `ParamSpec`

Parameter metadata used to drive UI widgets and defaults:
- name/default,
- label/description,
- type hints (`kind`),
- optional numeric bounds/options.

### `Stage2Pipeline`

Ordered executor of `CutStep` instances. Steps run in list order; each step receives the current context and can add/override keys.

### `CutRegistry`

Name-to-constructor registry used by config loading/UI to instantiate steps from YAML `name` entries.

## `active_mask` convention

`active_mask` is the convention for non-destructive filtering:
- filters should update this mask instead of deleting hits,
- downstream producers should honor it when selecting inputs.

This preserves provenance and allows toggling/replaying with different step settings.

## Filters vs producers

- **Filter:** primarily modifies eligibility (e.g., updates `active_mask`).
- **Producer:** derives higher-level objects (e.g., `clusters`) from current context.

A step can technically emit any context keys, but these roles help keep pipeline semantics clear.

## Current implemented steps

### `repeated_pixel_filter`

- Type: filter.
- Purpose: detect high-occupancy repeated pixels and deactivate associated hits.
- Key outputs:
  - `active_mask`
  - `repeated_pixel_mask`
  - `n_repeated_pixel_hits`
  - `n_repeated_pixels`

### `dbscan_cluster_producer`

- Type: producer.
- Purpose: run DBSCAN clustering on currently active, far-from-muon-region hits.
- Key output:
  - `clusters`

## Execution order matters

Because context is updated step-by-step, ordering changes behavior. Example: putting a filter before DBSCAN changes which hits are eligible for clustering.
