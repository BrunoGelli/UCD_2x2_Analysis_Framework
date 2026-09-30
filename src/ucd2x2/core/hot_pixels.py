"""Read-only FLOW access, hardware-pixel statistics, and shared event cleaning.

No source dataset is modified. Pickles are trusted, local analysis products, NOT
an interchange format for untrusted files. Thresholds act on original event hits.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import os
import pickle
import tempfile

import h5py
import numpy as np

FIELDS = ("io_group", "io_channel", "chip_id", "channel_id")
SCHEMA = "ucd2x2.hot-pixels.v1"
STAT_NAMES = ("total_hits", "events_with_hit", "events_with_2plus_hits",
              "events_with_3plus_hits", "events_with_4plus_hits", "max_hits_in_event")


def pixel_ids(hits):
    """Collision-free 4x16-bit IDs; never silently substitute drift coordinates.

    io_channel is the recorded route, not a tile number. Distinct routing aliases
    are deliberately NOT merged without a validated geometry/network mapping.
    """
    missing = set(FIELDS) - set(hits.dtype.names or ())
    if missing:
        raise ValueError(f"Hardware pixel fields missing: {sorted(missing)}. "
                         "Use calibrated FLOW hits with all four hardware IDs.")
    ids = np.zeros(len(hits), dtype=np.uint64)
    for field in FIELDS:
        col = hits[field]
        if col.ndim != 1 or not np.issubdtype(col.dtype, np.integer):
            raise ValueError(f"{field} must be a scalar integer field")
        if np.any(col < 0) or np.any(col > 65535):
            raise ValueError(f"{field} is outside the supported 0..65535 range")
        ids = (ids << np.uint64(16)) | col.astype(np.uint64)
    return ids


def decode_pixel(value):
    value = int(value)
    return tuple((value >> shift) & 65535 for shift in (48, 32, 16, 0))


def file_stamp(path):
    path = Path(path).expanduser().resolve()
    stat = path.stat()
    return {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


class _Rows:
    """Bounded read-ahead cache, including sorted sparse gathers with duplicates."""
    def __init__(self, dataset, block_rows):
        self.ds, self.block_rows = dataset, max(1, int(block_rows))
        self.start, self.stop, self.data = 0, 0, None

    def slice(self, start, stop):
        start, stop = int(start), int(stop)
        if not 0 <= start <= stop <= len(self.ds):
            raise ValueError(f"Invalid row range [{start}, {stop}) in {self.ds.name}")
        if start == stop:
            return np.empty((0, *self.ds.shape[1:]), dtype=self.ds.dtype)
        if self.data is not None and self.start <= start and stop <= self.stop:
            return self.data[start-self.start:stop-self.start]
        if stop - start > self.block_rows:
            return self.ds[start:stop]
        self.start = start
        self.stop = min(len(self.ds), max(stop, start + self.block_rows))
        self.data = self.ds[self.start:self.stop]
        return self.data[:stop-start]

    def gather(self, rows):
        rows = np.asarray(rows, dtype=np.int64)
        if not len(rows):
            return np.empty(0, dtype=self.ds.dtype)
        lo, hi = int(rows.min()), int(rows.max())
        if lo < 0 or hi >= len(self.ds):
            raise ValueError(f"Reference target outside {self.ds.name}")
        if hi-lo+1 <= self.block_rows:
            return self.slice(lo, hi+1)[rows-lo]
        if len(rows) == hi-lo+1 and np.all(np.diff(rows) == 1):
            return self.slice(lo, hi+1)
        unique, inverse = np.unique(rows, return_inverse=True)
        return self.ds[unique][inverse]


class EventHitReader:
    """Resolve event -> hit reference rows, NOT ref_region as direct hit offsets.

    Inputs must contain reconstructed charge/events and calibrated hits. Raw
    PACMAN packet files are not FLOW input. All file handles are read-only.
    """
    def __init__(self, path, hit_type="prompt", block_rows=250_000):
        if hit_type not in ("prompt", "final"):
            raise ValueError("hit_type must be prompt or final")
        if block_rows < 1:
            raise ValueError("block_rows must be positive")
        self.source = file_stamp(path)
        self.hit_type = hit_type
        self.h5 = h5py.File(self.source["path"], "r")
        try:
            target = f"charge/calib_{hit_type}_hits"
            self.events = self.h5["charge/events/data"]
            self.hits = self.h5[target + "/data"]
            refbase = f"charge/events/ref/{target}"
            self.regions = self.h5[refbase + "/ref_region"][:]
            self.refs = self.h5[refbase + "/ref"]
            if self.refs.ndim != 2 or self.refs.shape[1] != 2:
                raise ValueError("Expected event/hit reference pairs of shape (N, 2)")
            if len(self.regions) != len(self.events):
                raise ValueError("Event/ref_region lengths disagree")
            if not {"start", "stop"} <= set(self.regions.dtype.names or ()):
                raise ValueError("ref_region needs start and stop fields")
            self._hit_rows = _Rows(self.hits, block_rows)
            self._ref_rows = _Rows(self.refs, block_rows)
        except Exception:
            self.h5.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.h5.close()

    def __len__(self):
        return len(self.events)

    def signature(self):
        return dict(self.source, hit_type=self.hit_type, n_events=len(self),
                    n_hits=len(self.hits), hit_dtype=repr(self.hits.dtype.descr))

    def check_unchanged(self):
        if file_stamp(self.source["path"]) != self.source:
            raise RuntimeError("Source changed during processing; use a completed FLOW file")

    def get(self, index):
        index = int(index)
        if not 0 <= index < len(self):
            raise IndexError(f"Event index {index} outside 0..{len(self)-1}")
        region = self.regions[index]
        pairs = self._ref_rows.slice(region["start"], region["stop"])
        if len(pairs) and np.any(pairs[:, 0] != index):
            raise ValueError(f"Event {index} has inconsistent reference source rows")
        return self._hit_rows.gather(pairs[:, 1])

    def event_id(self, index):
        row = self.events[int(index)]
        return int(row["id"]) if "id" in (self.events.dtype.names or ()) else int(index)


@dataclass(frozen=True)
class CleaningPolicy:
    event_max_hits: int = 3
    global_mean_max: float | None = 1.0
    max_event_fraction: float | None = None
    drop_disabled: bool = True

    def __post_init__(self):
        if self.event_max_hits < 0:
            raise ValueError("event_max_hits must be >=0 (0 disables the local cut)")
        if self.global_mean_max is not None and (not np.isfinite(self.global_mean_max) or self.global_mean_max <= 0):
            raise ValueError("global_mean_max must be positive, or None")
        if self.max_event_fraction is not None and (not np.isfinite(self.max_event_fraction) or not 0 <= self.max_event_fraction <= 1):
            raise ValueError("max_event_fraction must be in [0,1], or None")
        if self.max_event_fraction == 1:
            object.__setattr__(self, "max_event_fraction", None)


class PixelAccumulator:
    """Vectorized per-event uniqueness and batched reductions, no per-hit dict loop."""
    def __init__(self, flush_pairs=250_000):
        self.keys = np.empty(0, dtype=np.uint64)
        self.stats = np.zeros((0, len(STAT_NAMES)), dtype=np.uint64)
        self.n_events, self.n_hits = 0, 0
        self.flush_pairs = max(1, int(flush_pairs))
        self._ids, self._counts, self._buffered = [], [], 0

    def add(self, hits):
        ids, counts = np.unique(pixel_ids(hits), return_counts=True)
        self.n_events += 1
        self.n_hits += len(hits)
        if len(ids):
            self._ids.append(ids)
            self._counts.append(counts.astype(np.uint64))
            self._buffered += len(ids)
        if self._buffered >= self.flush_pairs:
            self.flush()

    def flush(self):
        if not self._buffered:
            return
        ids = np.concatenate(self._ids)
        counts = np.concatenate(self._counts)
        unique, inverse = np.unique(ids, return_inverse=True)
        block = np.zeros((len(unique), len(STAT_NAMES)), dtype=np.uint64)
        np.add.at(block[:, 0], inverse, counts)
        for col, minimum in enumerate((1, 2, 3, 4), start=1):
            np.add.at(block[:, col], inverse, (counts >= minimum).astype(np.uint64))
        np.maximum.at(block[:, 5], inverse, counts)
        keys = np.union1d(self.keys, unique)
        merged = np.zeros((len(keys), len(STAT_NAMES)), dtype=np.uint64)
        merged[np.searchsorted(keys, self.keys)] = self.stats
        rows = np.searchsorted(keys, unique)
        merged[rows, :5] += block[:, :5]
        merged[rows, 5] = np.maximum(merged[rows, 5], block[:, 5])
        self.keys, self.stats = keys, merged
        self._ids.clear(); self._counts.clear(); self._buffered = 0


def _atomic_pickle(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            name = stream.name
            pickle.dump(payload, stream, protocol=pickle.HIGHEST_PROTOCOL)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name is not None and os.path.exists(name):
            os.unlink(name)


class HotPixelMask:
    def __init__(self, payload):
        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
            raise ValueError("Unsupported/legacy mask. Rebuild it with build-hot-mask")
        self.payload = payload
        self.keys = np.asarray(payload["keys"], dtype=np.uint64)
        self.stats = np.asarray(payload["stats"], dtype=np.uint64)
        self.n_events = int(payload["source"]["n_events"])
        if self.stats.shape != (len(self.keys), len(STAT_NAMES)) or np.any(self.keys[1:] <= self.keys[:-1]):
            raise ValueError("Invalid mask statistics or unsorted/duplicate pixel keys")
        self.policy = CleaningPolicy(**payload["policy"])

    @classmethod
    def load(cls, path):
        """Only load trusted PKLs; pickle can execute arbitrary Python code."""
        with open(path, "rb") as stream:
            return cls(pickle.load(stream))

    def save(self, path):
        if Path(path).resolve() == Path(self.payload["source"]["path"]).resolve():
            raise ValueError("Mask output cannot overwrite the source HDF5")
        _atomic_pickle(path, self.payload)

    def validate(self, reader):
        if self.payload["source"] != reader.signature():
            raise ValueError("Mask/source mismatch (path, size, mtime, collection, or schema). "
                             "Build a mask for this exact completed FLOW file")

    def bad_pixels(self, policy=None):
        policy = policy or self.policy
        bad = np.zeros(len(self.keys), dtype=bool)
        if policy.global_mean_max is not None:
            bad |= self.stats[:, 0] > policy.global_mean_max * self.n_events
        if policy.max_event_fraction is not None:
            bad |= self.stats[:, 1] > policy.max_event_fraction * self.n_events
        return self.keys[bad]

    def summary(self, policy=None):
        return {"n_events": self.n_events, "n_pixels": len(self.keys),
                "n_hot_pixels": len(self.bad_pixels(policy)),
                "n_associated_hits": int(self.payload["n_associated_hits"])}


def build_hot_mask(input_h5, output=None, hit_type="prompt", policy=None,
                   block_rows=250_000, progress=None):
    accumulator = PixelAccumulator()
    with EventHitReader(input_h5, hit_type, block_rows) as reader:
        # Fail before an expensive scan, including for an empty dataset.
        pixel_ids(np.empty(0, dtype=reader.hits.dtype))
        for index in range(len(reader)):
            accumulator.add(reader.get(index))
            if progress is not None and ((index+1) % 1000 == 0 or index+1 == len(reader)):
                progress(index+1, len(reader))
        accumulator.flush()
        reader.check_unchanged()
        payload = {"schema": SCHEMA, "source": reader.signature(),
                   "pixel_fields": FIELDS, "stat_names": STAT_NAMES,
                   "keys": accumulator.keys, "stats": accumulator.stats,
                   "n_associated_hits": accumulator.n_hits,
                   "created_utc": datetime.now(timezone.utc).isoformat(),
                   "policy": asdict(policy or CleaningPolicy())}
    mask = HotPixelMask(payload)
    if output is not None:
        mask.save(output)
    return mask


class EventCleaner:
    def __init__(self, mask=None, policy=None):
        self.policy = policy or (mask.policy if mask is not None else CleaningPolicy())
        self.bad = mask.bad_pixels(self.policy) if mask is not None else np.empty(0, dtype=np.uint64)

    def apply(self, hits):
        """Return (keep_mask, diagnostic_counts); original hits remain untouched.

        Local multiplicities are computed BEFORE any other removal. Removal
        counters are disjoint (invalid, disabled, global, local), in that order.
        """
        ids = pixel_ids(hits)
        keep = np.ones(len(hits), dtype=bool)
        report = {"raw_hits": len(hits)}
        invalid = np.zeros(len(hits), dtype=bool)
        for field in ("x", "y", "z", "Q"):
            if field not in (hits.dtype.names or ()):
                raise ValueError(f"Calibrated hit field '{field}' missing")
            invalid |= ~np.isfinite(hits[field])
        disabled = hits["is_disabled"].astype(bool) if self.policy.drop_disabled and "is_disabled" in hits.dtype.names else np.zeros(len(hits), dtype=bool)
        global_bad = np.isin(ids, self.bad)
        local_bad = np.zeros(len(hits), dtype=bool)
        if self.policy.event_max_hits and len(hits):
            _, inverse, counts = np.unique(ids, return_inverse=True, return_counts=True)
            local_bad = counts[inverse] > self.policy.event_max_hits
        for name, rejected in (("invalid", invalid), ("disabled", disabled),
                               ("global", global_bad), ("local", local_bad)):
            report[f"removed_{name}"] = int(np.count_nonzero(keep & rejected))
            keep &= ~rejected
        report["clean_hits"] = int(keep.sum())
        return keep, report


def product_stem(path, hit_type="prompt"):
    path = Path(path).expanduser().resolve()
    digest = hashlib.sha256(str(path).encode()).hexdigest()[:12]
    return f"{path.name}.{digest}.{hit_type}"
