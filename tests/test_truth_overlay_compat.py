import h5py
import numpy as np

from ucd2x2.core.io import FlowFile
from ucd2x2.display.viz import make_plotly_3d, truth_trajectory_overlay_diagnostic


def _dummy_hits(n=3):
    dt = np.dtype([("x", "f4"), ("y", "f4"), ("z", "f4"), ("Q", "f4"), ("t_drift", "f4"), ("ts_pps", "f4")])
    return np.array([(1, 2, 3, 4, 5, 6)] * n, dtype=dt)


def test_trajectory_overlay_scalar_fields_drawable():
    dt = np.dtype([("x_start", "f4"), ("y_start", "f4"), ("z_start", "f4"), ("x_end", "f4"), ("y_end", "f4"), ("z_end", "f4")])
    tr = np.array([(0, 0, 0, 1, 1, 1)], dtype=dt)
    ok, reason = truth_trajectory_overlay_diagnostic(tr)
    assert ok
    assert "scalar" in reason


def test_trajectory_overlay_xyz_vector_fields_drawable():
    dt = np.dtype([("xyz_start", "f4", (3,)), ("xyz_end", "f4", (3,))])
    tr = np.array([([0, 1, 2], [3, 4, 5])], dtype=dt)
    ok, reason = truth_trajectory_overlay_diagnostic(tr)
    assert ok
    assert "xyz_start" in reason


def test_trajectory_overlay_missing_fields_reports_reason():
    dt = np.dtype([("traj_id", "i4")])
    tr = np.array([(1,)], dtype=dt)
    ok, reason = truth_trajectory_overlay_diagnostic(tr)
    assert not ok
    assert "missing trajectory coordinates" in reason


def test_get_truth_vertices_falls_back_to_mc_hdr(tmp_path):
    path = tmp_path / "mini_hdr.h5"
    with h5py.File(path, "w") as h5:
        h5.create_dataset("charge/events/data", data=np.array([(0,)], dtype=np.dtype([("id", "i4")])))
        h5.create_dataset("charge/events/ref/charge/calib_prompt_hits/ref_region", data=np.array([(0, 0)], dtype=np.dtype([("start", "i8"), ("stop", "i8")])))
        h5.create_dataset("charge/calib_prompt_hits/data", data=np.array([], dtype=np.dtype([("Q", "f4")])))
        seg_dt = np.dtype([("event_id", "i4"), ("vertex_id", "i4"), ("segment_id", "i4")])
        h5.create_dataset("mc_truth/segments/data", data=np.array([(11, 7, 0)], dtype=seg_dt))
        hdr_dt = np.dtype([("event_id", "i4"), ("vertex_id", "i4"), ("vertex", "f4", (4,))])
        h5.create_dataset("mc_truth/mc_hdr/data", data=np.array([(11, 7, [1, 2, 3, 4])], dtype=hdr_dt))
    ff = FlowFile.open(str(path))
    ff.get_truth_segments_for_event = lambda event_index, hit_type="prompt": ff.h5["mc_truth/segments/data"][:]
    try:
        out = ff.get_truth_vertices(0, mode="backtrack")
        assert out is not None and len(out) == 1 and "vertex" in (out.dtype.names or ())
    finally:
        ff.close()


def test_vertex_plotting_without_interaction_id():
    vdt = np.dtype([("event_id", "i4"), ("vertex_id", "i4"), ("vertex", "f4", (4,))])
    vtx = np.array([(3, 4, [1, 2, 3, 9])], dtype=vdt)
    fig = make_plotly_3d(_dummy_hits(), mc_vertices=vtx)
    names = [tr.name for tr in fig.data]
    assert "MC vertices" in names
