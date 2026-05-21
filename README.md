# UCD 2x2 Analysis Framework

The **UCD 2x2 Analysis Framework** is an incremental analysis and visualization toolkit for ndlar_flow-like HDF5 event data.

Today, the repository provides:
- an interactive Panel event display,
- a configurable Stage 2 pipeline editor,
- YAML-backed Stage 2 pipeline definitions,
- a minimal Stage 2 batch runner,
- and an installable `ucd2x2` CLI entry point.

The codebase is intentionally evolving in small, testable steps while preserving existing behavior.

## Current implemented scope

Implemented now:
- **Event display** (`src/ucd2x2/display/app_panel.py`) for opening HDF5 data, navigating events, plotting hits, and viewing analysis overlays.
- **Stage 2 pipeline abstractions** (`CutStep`, `StepResult`, `Stage2Pipeline`, `CutRegistry`, `ParamSpec`).
- **Pipeline UI wiring** for editing ordered steps and parameters from the display.
- **YAML config loading/saving** for pipeline definitions.
- **Current Stage 2 steps**:
  - `repeated_pixel_filter`
  - `dbscan_cluster_producer`
- **Batch-mode Stage 2 runner** and JSON summary output.

Planned architecture stages are documented in `docs/architecture.md`.

## Quickstart installation

```bash
pip install -e .
```

Optional test dependency:

```bash
pip install pytest
```

Run tests:

```bash
pytest -q
```

## Event display

Launch with sample data:

```bash
ucd2x2 event-display tests/sample_data.hdf5
```

Equivalent direct Panel command:

```bash
panel serve src/ucd2x2/display/app_panel.py --show --args --h5 tests/sample_data.hdf5
```

More usage details: `docs/event_display.md`.

## Stage 2 batch

Run Stage 2 with a YAML pipeline and write JSON summary:

```bash
ucd2x2 stage2-run \
  --input tests/sample_data.hdf5 \
  --config configs/stage2/repeated_pixel_then_dbscan.yaml \
  --output /tmp/stage2_summary.json
```

More details: `docs/batch_runner.md`.

## YAML config concept

Stage 2 behavior is defined by YAML files that declare an **ordered** `pipeline` list of named steps, each with `enabled` and `params` fields. Step order is execution order.

Example configs live in:
- `configs/stage2/dbscan_default.yaml`
- `configs/stage2/repeated_pixel_then_dbscan.yaml`

Reference: `docs/yaml_configs.md`.

## Repository layout

- `src/ucd2x2/` – package source.
- `src/ucd2x2/core/` – shared IO, geometry, clustering, and selection helpers.
- `src/ucd2x2/display/` – Panel event display and visualization code.
- `src/ucd2x2/stage2/` – Stage 2 pipeline, config loading, widgets/UI helpers, and batch runner.
- `src/ucd2x2/stage2/cuts/` – currently implemented Stage 2 steps.
- `configs/stage2/` – YAML pipeline examples.
- `tests/` – regression and smoke tests (includes `tests/sample_data.hdf5` fixture).
- `docs/` – architecture and usage documentation.

## Current limitations

- Stage 2 output is currently a JSON summary (not yet tag-enriched output HDF5).
- Only two Stage 2 steps are currently implemented.
- Stage 3/Stage 4 architecture is planned but not implemented in this repository yet.
- Configuration schema is intentionally minimal and may evolve with backward-compatible migration steps.

## Roadmap (high level)

- Keep Stage 2 logic reusable between event display and batch mode.
- Expand the registry of filters/producers while preserving ordered-pipeline semantics.
- Add future tag/provenance outputs and downstream consolidation/blinding stages.
- Continue incremental refactors with tests-first changes.

## Additional docs

- `docs/architecture.md`
- `docs/event_display.md`
- `docs/stage2_pipeline.md`
- `docs/yaml_configs.md`
- `docs/writing_cuts.md`
- `docs/batch_runner.md`
- `docs/development.md`
