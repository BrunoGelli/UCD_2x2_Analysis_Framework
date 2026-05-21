# UCD 2x2 Analysis Framework (incremental refactor)

## Event display

Run the event display with:

```bash
panel serve twobytwo_display/app_panel.py --show --args --h5 tests/sample_data.hdf5
```

## Stage 2 batch (minimal)

Run Stage 2 DBSCAN pipeline over one file and write JSON summary:

```bash
python -m twobytwo_display.stage2.run_stage2 --input tests/sample_data.hdf5 --config configs/stage2/dbscan_default.yaml --output stage2_summary.json
```
