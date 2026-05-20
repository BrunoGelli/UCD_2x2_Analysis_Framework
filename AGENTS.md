# Agent Instructions

This repository is being developed into the UCD 2x2 Analysis Framework.

## Current state

- The current working event display lives in `twobytwo_display/app_panel.py`.
- The event display opens ndlar_flow-like HDF5 files and displays event hits.
- A small committed HDF5 fixture is available at `tests/sample_data.hdf5`.
- The framework is being refactored gradually. Preserve existing behavior unless the task explicitly asks otherwise.

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

Run the event display manually:

```bash
panel serve -m twobytwo_display.app_panel --show --args --h5 tests/sample_data.hdf5
```

## Design rules

- Keep the event display as a frontend/viewer.
- Do not put new cut/tag/analysis logic directly into Panel callback code.
- Shared analysis logic should live in reusable modules.
- Stage 2 should tag packets/hits/objects rather than destructively deleting information.
- Batch mode and the event display should eventually call the same Stage 2 pipeline.
- Config files should store parameters/order, not Python logic.
- Keep changes small, tested, and backward compatible.
- Do not refactor unrelated IO, plotting, or truth-overlay behavior unless the task explicitly asks for it.

## Testing expectations

Before finishing a coding task, run:

```bash
pytest -q
```

At minimum, verify imports still work:

```bash
python -c "import twobytwo_display.app_panel"
```

For display changes, preserve this command:

```bash
panel serve -m twobytwo_display.app_panel --show --args --h5 tests/sample_data.hdf5
```
