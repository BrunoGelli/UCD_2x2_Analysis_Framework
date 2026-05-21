# Event display guide

## Launching the display

Primary command:

```bash
ucd2x2 event-display tests/sample_data.hdf5
```

Direct Panel equivalent:

```bash
panel serve src/ucd2x2/display/app_panel.py --show --args --h5 tests/sample_data.hdf5
```

Useful CLI options:
- `--no-show` – do not auto-open browser.
- `--port <N>` – set Panel server port.
- `--max-hits <N>` – pass max hit cap to `app_panel.py`.

## Opening the sample fixture

The repository includes `tests/sample_data.hdf5`. You can pass it directly at launch (above) or type it in the file path widget and click **Open**.

## Navigation

The display supports event navigation through:
- event slider,
- direct event index input,
- previous/next buttons,
- optional muon-only scan mode.

## Display options

Available controls include:
- hit type (`prompt`/`final`),
- color mode,
- max hits,
- point size,
- geometry overlay toggles,
- 2D/3D/analysis plotting panes.

## Truth overlay support

The UI includes truth-overlay options such as:
- enable/disable truth display,
- truth mode selection (`backtrack` or `window`),
- truth event/window controls,
- vertex toggles,
- muon-only truth filtering,
- segment draw limits.

Exact rendered overlays depend on available truth content in the input file.

## Stage 2 pipeline editor

The display includes an embedded Stage 2 editor that lets you:
- load a YAML pipeline,
- enable/disable steps,
- modify step parameters,
- reorder/remove/add steps,
- save YAML back to disk.

## Loading/saving YAML configs

Use the Stage 2 config path field plus **Load Stage 2 config** / **Save Stage 2 config** buttons to round-trip pipeline configuration.

Recommended starting configs:
- `configs/stage2/dbscan_default.yaml`
- `configs/stage2/repeated_pixel_then_dbscan.yaml`

## How cuts affect clustering

Clustering uses the current Stage 2 context. In the current setup:
- `repeated_pixel_filter` can deactivate hits by updating `active_mask`.
- `dbscan_cluster_producer` consumes active hits (plus muon-region selection) and emits clusters.

Therefore, toggling/reordering/configuring filters can change cluster counts and cluster properties.
