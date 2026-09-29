"""Candidate summaries using exactly the same read/clean path as the browser."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import csv
import hashlib
import json
import os
import tempfile

import numpy as np

from .hot_pixels import EventHitReader, EventCleaner, CleaningPolicy, pixel_ids


def mask_digest(mask):
    if mask is None:
        return None
    digest = hashlib.sha256(mask.keys.tobytes())
    digest.update(mask.stats.tobytes())
    return digest.hexdigest()


def nominal_volume_mask(hits, tolerance_cm=1.0):
    """Diagnostic only: stored coordinates in the existing module boxes, ±1 cm.

    This is NOT a timing correction or a validated physics selection.
    """
    from .geometry import module_boxes_cm
    inside = np.zeros(len(hits), dtype=bool)
    for box in module_boxes_cm().values():
        member = np.ones(len(hits), dtype=bool)
        for axis in ("x", "y", "z"):
            member &= ((hits[axis] >= getattr(box, axis+"min")-tolerance_cm)
                       & (hits[axis] <= getattr(box, axis+"max")+tolerance_cm))
        inside |= member
    return inside


def timestamp_span(hits):
    if not len(hits) or "ts_pps" not in (hits.dtype.names or ()):
        return 0
    values = hits["ts_pps"]
    values = values[np.isfinite(values)]
    return int(values.max())-int(values.min()) if len(values) else 0


def event_summary(hits):
    """Q remains signed and in the input file's units; no ADC/energy assumption."""
    q = np.asarray(hits["Q"], dtype=float)
    q = q[np.isfinite(q)]
    positive = q[q > 0]
    qpos = float(positive.sum(dtype=np.float64))
    result = {"total_Q": float(q.sum(dtype=np.float64)), "positive_Q": qpos,
              "n_unique_pixels": len(np.unique(pixel_ids(hits))),
              "largest_hit_Q_fraction": float(positive.max()/qpos) if qpos > 0 else 0.0}
    inside = nominal_volume_mask(hits)
    iq = np.asarray(hits["Q"][inside], dtype=float)
    result.update(n_in_nominal_volume=int(inside.sum()),
                  nominal_volume_fraction=float(inside.mean()) if len(hits) else 0.0,
                  Q_in_nominal_volume=float(iq[np.isfinite(iq)].sum()),
                  ts_pps_span=timestamp_span(hits))
    for axis in ("x", "y", "z"):
        coords = np.asarray(hits[axis], dtype=float)
        coords = coords[np.isfinite(coords)]
        result[f"{axis}_span_cm"] = float(np.ptp(coords)) if len(coords) else 0.0
    return result


def _atomic_text(path, writer):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                         dir=path.parent, delete=False) as stream:
            name = stream.name
            writer(stream)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def scan_events(input_h5, output, mask=None, policy=None, hit_type="prompt",
                block_rows=250_000, max_events=None, progress=None):
    if Path(output).resolve() == Path(input_h5).resolve():
        raise ValueError("CSV output cannot overwrite the source HDF5")
    if max_events is not None and max_events < 0:
        raise ValueError("max_events must be nonnegative")
    cleaner = EventCleaner(mask, policy)
    rows = []
    with EventHitReader(input_h5, hit_type, block_rows) as reader:
        if mask is not None:
            mask.validate(reader)
        n = len(reader) if max_events is None else min(int(max_events), len(reader))
        for index in range(n):
            raw = reader.get(index)
            keep, counts = cleaner.apply(raw)
            clean = raw[keep]
            rows.append(dict(event_index=index, event_id=reader.event_id(index), raw_ts_pps_span=timestamp_span(raw),
                             **counts, **event_summary(clean)))
            if progress is not None and ((index+1) % 1000 == 0 or index+1 == n):
                progress(index+1, n)
        reader.check_unchanged()
        metadata = {"schema": "ucd2x2.event-candidates.v1", "source": reader.signature(),
                    "policy": asdict(cleaner.policy), "mask_digest": mask_digest(mask),
                    "n_scanned": n, "sort": "total_Q descending (signed input units)",
                    "nominal_volume_tolerance_cm": 1.0,
                    "time_span_units": "stored ts_pps units, no conversion; diagnostic only"}
    rows.sort(key=lambda row: (-row["total_Q"], row["event_index"]))
    fields = ["event_index", "event_id", "raw_hits", "removed_invalid", "removed_disabled",
              "removed_global", "removed_local", "clean_hits", "total_Q", "positive_Q",
              "n_unique_pixels", "largest_hit_Q_fraction", "x_span_cm", "y_span_cm", "z_span_cm",
              "n_in_nominal_volume", "nominal_volume_fraction", "Q_in_nominal_volume",
              "ts_pps_span", "raw_ts_pps_span"]
    def write_csv(stream):
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    _atomic_text(output, write_csv)
    _atomic_text(str(output)+".json", lambda stream: json.dump(metadata, stream, indent=2))
    return rows


def load_candidates(path, reader, cleaner, mask=None):
    """Refuse stale rankings instead of mixing different files or cleaning policies."""
    meta_path = Path(str(path)+".json")
    if not meta_path.is_file():
        raise ValueError("Candidate metadata is missing; regenerate with scan-events")
    metadata = json.loads(meta_path.read_text())
    if (metadata.get("source") != reader.signature()
            or metadata.get("policy") != asdict(cleaner.policy)
            or metadata.get("mask_digest") != mask_digest(mask)):
        raise ValueError("Candidate/source/cleaning mismatch. Rerun scan-events with these settings")
    with open(path, newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        row["event_index"] = int(row["event_index"])
        row["total_Q"] = float(row["total_Q"])
        if not 0 <= row["event_index"] < len(reader):
            raise ValueError("Candidate event index outside this file")
    return sorted(rows, key=lambda row: (-row["total_Q"], row["event_index"]))
