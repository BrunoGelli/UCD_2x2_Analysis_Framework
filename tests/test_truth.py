import h5py
import numpy as np

from ucd2x2.core.io import FlowFile
from ucd2x2.core.truth import (
    build_trajectory_lookup,
    format_truth_ancestry,
    summarize_truth_event_tree,
    trace_trajectory_ancestry,
)


def _traj_array():
    dt = np.dtype([("event_id", "i4"), ("traj_id", "i4"), ("parent_id", "i4"), ("pdg_id", "i4")])
    return np.array([(1, 10, -1, 13), (1, 11, 10, 11), (1, 12, 11, 22)], dtype=dt)


def test_build_lookup_and_trace_chain():
    tr = _traj_array()
    lookup = build_trajectory_lookup(tr)
    seg_dt = np.dtype([("event_id", "i4"), ("traj_id", "i4"), ("dE", "f4")])
    seg = np.array((1, 12, 1.2), dtype=seg_dt)
    chain = trace_trajectory_ancestry(seg, lookup)
    assert len(chain) == 3
    assert int(chain[0]["traj_id"]) == 12
    assert int(chain[-1]["parent_id"]) < 0


def test_trace_missing_parent_and_cycle_protection():
    dt = np.dtype([("traj_id", "i4"), ("parent_id", "i4")])
    tr = np.array([(1, 2), (2, 1)], dtype=dt)
    lookup = build_trajectory_lookup(tr)
    chain = trace_trajectory_ancestry(tr[0], lookup, max_depth=10)
    assert any(isinstance(x, dict) and "cycle" in x.get("warning", "") for x in chain)

    tr2 = np.array([(4, 99)], dtype=dt)
    chain2 = trace_trajectory_ancestry(tr2[0], build_trajectory_lookup(tr2))
    assert any(isinstance(x, dict) and "missing parent" in x.get("warning", "") for x in chain2)


def test_format_and_summary_nonempty():
    tr = _traj_array()
    seg_dt = np.dtype([("event_id", "i4"), ("traj_id", "i4"), ("dE", "f4")])
    segs = np.array([(1, 12, 0.5)], dtype=seg_dt)
    txt = format_truth_ancestry(segs[0], trace_trajectory_ancestry(segs[0], build_trajectory_lookup(tr)))
    assert txt
    summary = summarize_truth_event_tree(segs, tr, max_entries=5, tables_available={"trajectories": "mc_truth/trajectories/data"})
    assert "Truth Tree" in summary


def test_flowfile_truth_accessors_missing_tables(tmp_path):
    path = tmp_path / "mini.h5"
    with h5py.File(path, "w") as h5:
        h5.create_dataset("charge/events/data", data=np.array([(0,)], dtype=np.dtype([("id", "i4")])))
        h5.create_dataset("charge/calib_prompt_hits/data", data=np.array([], dtype=np.dtype([("Q", "f4")])))
        h5.create_dataset(
            "charge/events/ref/charge/calib_prompt_hits/ref_region",
            data=np.array([(0, 0)], dtype=np.dtype([("start", "i8"), ("stop", "i8")])),
        )
    ff = FlowFile.open(str(path))
    try:
        avail = ff.get_truth_tables_available()
        assert avail["trajectories"] is None
        assert ff.get_truth_trajectories_for_event(0) is None
        assert ff.get_truth_mc_hdr_for_event(0) is None
        assert ff.get_truth_mc_stack_for_event(0) is None
    finally:
        ff.close()
