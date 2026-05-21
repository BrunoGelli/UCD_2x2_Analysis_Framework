from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from ..io import FlowFile
from .config import load_pipeline


def run_stage2_file(input_h5, config_path, output_summary_path=None, max_events=None) -> Dict[str, Any]:
    pipeline = load_pipeline(config_path)
    flow = FlowFile.open(str(input_h5))
    clusters_per_event = []
    n_failed = 0
    n_processed = 0
    total_repeated_pixel_hits = 0
    total_repeated_pixels = 0
    try:
        n_total = int(flow.n_events())
        n_target = n_total if max_events is None else min(n_total, int(max_events))
        for event_index in range(n_target):
            try:
                hits = flow.get_event_hits(event_index, hit_type="prompt")
                muon_track = flow.get_muon_track_for_event(event_index)
                event_id = flow.event_id(event_index)
                out = pipeline.run(
                    {
                        "hits": hits,
                        "event_index": event_index,
                        "event_id": event_id,
                        "muon_track": muon_track,
                    }
                )
                clusters = out.get("clusters", []) or []
                clusters_per_event.append(int(len(clusters)))
                total_repeated_pixel_hits += int(out.get("n_repeated_pixel_hits", 0) or 0)
                total_repeated_pixels += int(out.get("n_repeated_pixels", 0) or 0)
                n_processed += 1
            except Exception:
                n_failed += 1
                continue
    finally:
        flow.close()

    n_with_clusters = int(sum(1 for n in clusters_per_event if n > 0))
    total_clusters = int(sum(clusters_per_event))
    if clusters_per_event:
        cmin = int(min(clusters_per_event))
        cmax = int(max(clusters_per_event))
        cmean = float(total_clusters / len(clusters_per_event))
    else:
        cmin, cmax, cmean = 0, 0, 0.0

    summary = {
        "input_h5": str(input_h5),
        "config_path": str(config_path),
        "n_events_total": int(n_total),
        "n_events_processed": int(n_processed),
        "n_events_failed": int(n_failed),
        "n_events_with_clusters": n_with_clusters,
        "total_clusters": total_clusters,
        "clusters_per_event_min": cmin,
        "clusters_per_event_max": cmax,
        "clusters_per_event_mean": cmean,
        "total_repeated_pixel_hits": int(total_repeated_pixel_hits),
        "total_repeated_pixels": int(total_repeated_pixels),
    }

    if output_summary_path is not None:
        p = Path(output_summary_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(summary, indent=2, sort_keys=True))

    return summary


def _main(argv=None):
    parser = argparse.ArgumentParser(description="Run Stage 2 pipeline over one HDF5 file")
    parser.add_argument("--input", required=True, help="Input HDF5 file")
    parser.add_argument("--config", required=True, help="Stage 2 YAML config path")
    parser.add_argument("--output", default=None, help="Optional JSON summary output path")
    parser.add_argument("--max-events", type=int, default=None, help="Optional max number of events to process")
    args = parser.parse_args(argv)

    summary = run_stage2_file(args.input, args.config, output_summary_path=args.output, max_events=args.max_events)
    if args.output is None:
        print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    _main()
