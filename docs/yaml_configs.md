# Stage 2 YAML configs

Stage 2 config files define an **ordered pipeline**.

## Format

Top-level mapping:

- `pipeline`: list of step entries

Each step entry uses:
- `name` (string): registered step name.
- `enabled` (bool, optional; defaults true): whether step is active.
- `params` (mapping, optional): parameter values passed to step constructor.

Order in `pipeline` is execution order.

## Example: `configs/stage2/dbscan_default.yaml`

This file includes:
1. `repeated_pixel_filter` (currently disabled in this example).
2. `dbscan_cluster_producer` (currently disabled in this example).

Use this file as an editable baseline while enabling/tuning the specific steps you need.

## Example: `configs/stage2/repeated_pixel_then_dbscan.yaml`

This file enables both:
1. `repeated_pixel_filter`
2. `dbscan_cluster_producer`

The ordering encodes a common pattern: filter first, then cluster.

## Practical notes

- Unknown step names are rejected at load time.
- Non-boolean `enabled` and non-mapping `params` are rejected.
- The loader normalizes and validates shape before pipeline construction.
