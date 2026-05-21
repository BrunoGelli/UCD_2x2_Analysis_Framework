# UCD 2x2 Analysis Framework (incremental refactor)

## Event display

Run the event display with:

```bash
panel serve src/ucd2x2/display/app_panel.py --show --args --h5 tests/sample_data.hdf5
```

## Stage 2 batch (minimal)

Run Stage 2 DBSCAN pipeline over one file and write JSON summary:

```bash
python -m ucd2x2.stage2.run_stage2 --input tests/sample_data.hdf5 --config configs/stage2/dbscan_default.yaml --output stage2_summary.json
```


## CLI

Run the event display via the package CLI:

```bash
ucd2x2 event-display tests/sample_data.hdf5
```

Run Stage 2 via the package CLI:

```bash
ucd2x2 stage2-run --input tests/sample_data.hdf5 --config configs/stage2/repeated_pixel_then_dbscan.yaml --output /tmp/stage2_summary.json
```
