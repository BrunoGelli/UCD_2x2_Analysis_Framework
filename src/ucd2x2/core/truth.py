from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np


def _names(arr) -> Tuple[str, ...]:
    return tuple(arr.dtype.names or ()) if arr is not None else tuple()


def _first_existing(row: Any, candidates: Sequence[str], default=None):
    names = row.dtype.names or ()
    for c in candidates:
        if c in names:
            return row[c]
    return default


def build_trajectory_lookup(trajectories):
    if trajectories is None:
        return {}
    names = _names(trajectories)
    if "traj_id" not in names:
        return {}
    out: Dict[Any, Any] = {}
    for tr in trajectories:
        key = int(tr["traj_id"])
        if "event_id" in names:
            out[(int(tr["event_id"]), key)] = tr
        out[key] = tr
    return out


def find_trajectory_for_segment(segment, trajectory_lookup):
    if segment is None:
        return None
    names = segment.dtype.names or ()
    if "traj_id" not in names:
        return None
    tid = int(segment["traj_id"])
    if "event_id" in names and (int(segment["event_id"]), tid) in trajectory_lookup:
        return trajectory_lookup[(int(segment["event_id"]), tid)]
    return trajectory_lookup.get(tid)


def trace_trajectory_ancestry(segment_or_trajectory, trajectory_lookup, max_depth: int = 64):
    if segment_or_trajectory is None:
        return []
    row = find_trajectory_for_segment(segment_or_trajectory, trajectory_lookup)
    if row is None:
        row = segment_or_trajectory
    names = row.dtype.names or ()
    if "traj_id" not in names:
        return []
    chain = []
    visited = set()
    cur = row
    depth = 0
    while cur is not None and depth < max_depth:
        names = cur.dtype.names or ()
        if "traj_id" not in names:
            break
        tid = int(cur["traj_id"])
        if tid in visited:
            chain.append({"warning": f"cycle detected at traj_id={tid}"})
            break
        visited.add(tid)
        chain.append(cur)
        if "parent_id" not in names:
            break
        pid = int(cur["parent_id"])
        if pid < 0:
            break
        next_row = None
        if "event_id" in names and (int(cur["event_id"]), pid) in trajectory_lookup:
            next_row = trajectory_lookup.get((int(cur["event_id"]), pid))
        if next_row is None:
            next_row = trajectory_lookup.get(pid)
        if next_row is None:
            chain.append({"warning": f"missing parent traj_id={pid}"})
            break
        cur = next_row
        depth += 1
    return chain


def _fmt_row(row):
    if isinstance(row, dict):
        return f"- {row.get('warning','warning')}"
    names = row.dtype.names or ()
    bits = []
    for k in ["traj_id", "parent_id", "pdg_id", "start_process", "end_process", "t_start"]:
        if k in names:
            bits.append(f"{k}={row[k]}")
    xyz = None
    if all(k in names for k in ["x_start", "y_start", "z_start"]):
        xyz = f"x/y/z=({float(row['x_start']):.2f},{float(row['y_start']):.2f},{float(row['z_start']):.2f})"
    elif "xyz_start" in names:
        p = row["xyz_start"]
        xyz = f"xyz_start=({float(p[0]):.2f},{float(p[1]):.2f},{float(p[2]):.2f})"
    if xyz:
        bits.append(xyz)
    return "- " + ", ".join(bits)


def format_truth_ancestry(segment, ancestry_chain):
    lines = []
    if segment is not None:
        s_names = segment.dtype.names or ()
        de = f", dE={float(segment['dE']):.4g}" if "dE" in s_names else ""
        tid = int(segment["traj_id"]) if "traj_id" in s_names else "?"
        lines.append(f"Deposit traj_id={tid}{de}")
    for row in ancestry_chain:
        lines.append(_fmt_row(row))
    return "\n".join(lines)


def summarize_truth_event_tree(segments, trajectories, *, max_entries: int = 10, tables_available: Optional[Dict[str, Optional[str]]] = None):
    if trajectories is None:
        return "Truth tree unavailable: no trajectories table found."
    lines = ["### Truth Tree", ""]
    if tables_available is not None:
        lines.append("- tables:")
        for k, v in tables_available.items():
            lines.append(f"  - {k}: {'missing' if not v else v}")
    nseg = 0 if segments is None else len(segments)
    lines.append(f"- segments: **{nseg}**")
    lines.append(f"- trajectories: **{len(trajectories)}**")
    if segments is None or len(segments) == 0:
        return "\n".join(lines + ["", "No truth segments found for this event."])
    order = np.arange(len(segments))
    names = _names(segments)
    if "dE" in names:
        order = np.argsort(-segments["dE"].astype(float))
    lookup = build_trajectory_lookup(trajectories)
    lines.append("")
    for i, idx in enumerate(order[: max(0, int(max_entries))]):
        seg = segments[int(idx)]
        chain = trace_trajectory_ancestry(seg, lookup)
        lines.append(f"#### Deposit {i}")
        lines.append(format_truth_ancestry(seg, chain))
    return "\n".join(lines)
