# Stage 2 batch runner

## CLI command

Run Stage 2 over one HDF5 file:

```bash
ucd2x2 stage2-run --input <input_h5> --config <stage2_yaml> --output <summary_json>
```

Optional:
- `--max-events N` limits processed events.

## Inputs

- **Input file:** ndlar_flow-like HDF5 path.
- **YAML config:** ordered Stage 2 pipeline definition.

## Output

Current output is a JSON summary with metrics including:
- `n_events_total`
- `n_events_processed`
- `n_events_failed`
- `n_events_with_clusters`
- `total_clusters`
- `clusters_per_event_min`
- `clusters_per_event_max`
- `clusters_per_event_mean`
- `total_repeated_pixel_hits`
- `total_repeated_pixels`

## Current limitations

- No tag-enriched output HDF5 is written yet.
- Summary focuses on aggregate counters/statistics.
- Error handling currently counts failed events and continues.

## Forward direction

Planned evolution is toward writing Stage 2 tag/provenance products to HDF5 for downstream stages, while retaining concise JSON summaries for quick checks.
