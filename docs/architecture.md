# Architecture overview

This project is organized around a staged analysis model.

## Stage model

### Stage 1: preprocessing (planned/design context)

Stage 1 is the input-preparation phase. Conceptually it normalizes or derives representations needed by later stages, while preserving source information.

**Status:** planned (not separately formalized in this repo yet).

### Stage 2: tagging/cut pipeline (implemented)

Stage 2 is an ordered, configurable pipeline of reusable steps (`CutStep`) that operate on event context and return updates (`StepResult`).

Current implementation supports:
- filters that update `active_mask` (e.g., `repeated_pixel_filter`),
- producers that consume active hits and emit higher-level objects (e.g., DBSCAN clusters).

Stage 2 is driven by YAML config (`pipeline` list with ordered steps).

**Status:** implemented and used in both display and batch mode.

### Stage 3: per-file MCP analysis (planned)

Stage 3 is intended for per-file analysis products and MCP-like summaries derived from Stage 2 outputs.

**Status:** planned.

### Stage 4: consolidation/blinding (planned)

Stage 4 is intended for combining outputs across files/runs and for blinding-aware workflows.

**Status:** planned.

## Implemented vs planned at a glance

- Implemented now: Stage 2 framework + event display integration + batch runner.
- Planned: dedicated Stage 1/Stage 3/Stage 4 implementations.

## Why YAML is the source of truth

YAML files are the canonical representation of Stage 2 pipeline intent because they:
- separate analysis configuration from Python code,
- make step ordering explicit and reviewable,
- are easy to save/load from UI and batch contexts,
- support reproducibility by pinning names, enable flags, and parameter values.

## Shared Stage 2 in display and batch

Both modes rely on the same Stage 2 pipeline abstractions:
- Event display: edits/loads/saves YAML and applies steps in interactive event context.
- Batch runner: loads YAML, runs the same step chain across events, and summarizes results.

This shared pipeline model reduces divergence and keeps analysis behavior consistent across workflows.
