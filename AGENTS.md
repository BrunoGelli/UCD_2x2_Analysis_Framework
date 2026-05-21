# Agent Instructions

This repository is being developed into the UCD 2x2 Analysis Framework.

## Current state

- Python package layout is `src/ucd2x2`.
- The package imports as `ucd2x2`.
- The current working event display lives in `src/ucd2x2/display/app_panel.py`.
- A small committed HDF5 fixture is available at `tests/sample_data.hdf5`.
- Framework work is incremental; preserve existing behavior unless explicitly asked otherwise.

## Setup

Use editable install during development:

```bash
pip install -e .
```

Install test tools if needed:

```bash
pip install pytest
```

Run tests:

```bash
pytest -q
```

## Key commands

Event display (CLI):

```bash
ucd2x2 event-display tests/sample_data.hdf5
```

Event display (direct Panel command):

```bash
panel serve src/ucd2x2/display/app_panel.py --show --args --h5 tests/sample_data.hdf5
```

Stage 2 batch (CLI):

```bash
ucd2x2 stage2-run --input tests/sample_data.hdf5 --config configs/stage2/repeated_pixel_then_dbscan.yaml --output /tmp/stage2_summary.json
```

Stage 2 batch (module):

```bash
python -m ucd2x2.stage2.run_stage2 --input tests/sample_data.hdf5 --config configs/stage2/repeated_pixel_then_dbscan.yaml --output /tmp/stage2_summary.json
```

## Design rules

- Keep the event display as a frontend/viewer.
- Do not put new cut/tag/analysis logic directly into Panel callback code.
- Shared analysis logic should live in reusable modules.
- Stage 2 should tag packets/hits/objects rather than destructively deleting information.
- Batch mode and the event display should call the same Stage 2 pipeline semantics.
- Config files should store parameters/order, not Python logic.
- Keep changes small, tested, and backward compatible.
- Do not refactor unrelated IO, plotting, or truth-overlay behavior unless explicitly asked.

## Testing expectations

Before finishing coding tasks, run:

```bash
pytest -q
python -c "import ucd2x2.display.app_panel"
```

For display-facing changes, preserve this command:

```bash
panel serve src/ucd2x2/display/app_panel.py --show --args --h5 tests/sample_data.hdf5
```
