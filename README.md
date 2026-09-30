# UCD 2x2 Analysis Framework

The **UCD 2x2 Analysis Framework** is an incremental analysis and visualization toolkit for ndlar_flow-like HDF5 event data.

Today, the repository provides:
- an interactive Panel event display,
- a read-only hardware hot-pixel mask and candidate-browser workflow,
- multi-file mask construction on compute nodes,
- a configurable Stage 2 pipeline editor,
- YAML-backed Stage 2 pipeline definitions,
- a minimal Stage 2 batch runner,
- and an installable `ucd2x2` CLI entry point.

The codebase is intentionally evolving in small, testable steps while preserving existing behavior.

## NERSC cleaning workflow

See **[the step-by-step NERSC tutorial](docs/nersc_workflow.md)** for compute-node
batch submission, mask reuse, candidate navigation and the authenticated Panel URL.
No source-file copies or edits are required.

```bash
# First two commands: on allocated compute nodes.
ucd2x2 build-hot-mask RUN.FLOW.hdf5 -o RUN.hot_pixels.pkl
ucd2x2 scan-events RUN.FLOW.hdf5 --hot-mask RUN.hot_pixels.pkl -o RUN.candidates.csv

# NERSC Jupyter terminal: prints the URL to open in a separate browser tab.
ucd2x2 event-display RUN.FLOW.hdf5 --hot-mask RUN.hot_pixels.pkl \
    --candidates RUN.candidates.csv --jupyter --port 5006 --no-show
```

For many files use `scripts/build_masks.py` and `slurm/build_masks.slurm`, as
documented in the tutorial. Only load trusted PKLs. Source and cleaning-policy
mismatches are rejected; high cleaned charge is a candidate score, not a cosmic
classification. The tile-5/IOG-6 highlight has been removed.

## Current implemented scope

Implemented now:
- **Event display** (`src/ucd2x2/display/app_panel.py`) for opening HDF5 data, navigating events, plotting hits, and viewing analysis overlays.
- **Cleaned browser** (`src/ucd2x2/display/clean_panel.py`) for shared hardware cleaning, raw comparison, provenance-checked rankings and geometry/time diagnostics.
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

Launch the original full Stage-2/truth-overlay display with sample data:

```bash
ucd2x2 event-display tests/sample_data.hdf5
```

Equivalent direct Panel command:

```bash
panel serve src/ucd2x2/display/app_panel.py --show --args --h5 tests/sample_data.hdf5
```

More usage details: `docs/event_display.md` and `docs/nersc_workflow.md`.

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
- `src/ucd2x2/core/` – shared IO, geometry, clustering, selection and hot-pixel helpers.
- `src/ucd2x2/display/` – Panel event displays and visualization code.
- `src/ucd2x2/stage2/` – Stage 2 pipeline, config loading, widgets/UI helpers, and batch runner.
- `configs/stage2/` – YAML pipeline examples.
- `scripts/` and `slurm/` – multi-file processing and NERSC compute-node launcher.
- `tests/` – regression and smoke tests (includes `tests/sample_data.hdf5` fixture).
- `docs/` – architecture and usage documentation.

## Current limitations

- Stage 2 output is currently a JSON summary (not yet tag-enriched output HDF5).
- Only two Stage 2 steps are currently implemented.
- Stage 3/Stage 4 architecture is planned but not implemented in this repository yet.
- Configuration schema is intentionally minimal and may evolve with backward-compatible migration steps.
- Hardware-mask cleaning/candidate browsing is a dedicated real-data frontend; the legacy Stage-2/truth editor and batch runner retain their existing semantics.

## Roadmap (high level)

- Keep Stage 2 logic reusable between event display and batch mode.
- Expand the registry of filters/producers while preserving ordered-pipeline semantics.
- Add future tag/provenance outputs and downstream consolidation/blinding stages.
- Continue incremental refactors with tests-first changes.

## Additional docs

- `docs/nersc_workflow.md`
- `docs/architecture.md`
- `docs/stage2_pipeline.md`
- `docs/yaml_configs.md`
- `docs/writing_cuts.md`
- `docs/batch_runner.md`
- `docs/development.md`
