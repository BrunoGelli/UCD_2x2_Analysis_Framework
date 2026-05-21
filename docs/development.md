# Development guide

## Editable install

```bash
pip install -e .
```

## Run tests

```bash
pytest -q
```

## Sample data fixture

Use `tests/sample_data.hdf5` for local development and regression tests.

## Package layout

- `src/ucd2x2/core/` – shared low-level analysis helpers.
- `src/ucd2x2/display/` – Panel event display.
- `src/ucd2x2/stage2/` – Stage 2 framework, config, UI integration, batch runner.
- `src/ucd2x2/stage2/cuts/` – concrete step implementations.

## Expected checks before PR

Run at minimum:

```bash
pytest -q
python -c "import ucd2x2.display.app_panel"
```

If changing display-related docs or behavior, verify launch command still works:

```bash
panel serve src/ucd2x2/display/app_panel.py --show --args --h5 tests/sample_data.hdf5
```

## Guidance for Codex/agent use

- Keep changes small and focused.
- Avoid unrelated refactors in the same PR.
- Preserve existing runtime behavior unless explicitly requested.
- Prefer documentation updates that reference concrete files/commands already in the repo.
