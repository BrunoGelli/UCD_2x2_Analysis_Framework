import numpy as np
import pytest

from ucd2x2.stage2.config import default_registry, load_pipeline_config, pipeline_from_dict
from ucd2x2.stage2.cuts import DBSCANClusterProducer, RepeatedPixelFilter
from ucd2x2.stage2.pipeline import Stage2Pipeline


def _hits_for_repeated_pixels():
    dtype = [("x", "f4"), ("y", "f4"), ("z", "f4"), ("Q", "f4")]
    hits = np.zeros(8, dtype=dtype)
    hits["x"] = np.linspace(0, 1, 8)
    hits["Q"] = 1
    hits["y"] = np.array([0, 0, 0, 0, 1, 2, 3, 4], dtype=float)
    hits["z"] = np.array([0, 0, 0, 0, 1, 2, 3, 4], dtype=float)
    return hits


def test_repeated_pixel_filter_masks_repeated_pixels():
    hits = _hits_for_repeated_pixels()
    step = RepeatedPixelFilter(max_hits_per_pixel=2, pixel_fields="y,z", round_decimals=3)
    out = step.run({"hits": hits}).data
    assert out["n_repeated_pixels"] == 1
    assert out["n_repeated_pixel_hits"] == 4
    assert int(np.sum(out["active_mask"])) == 4


def test_repeated_pixel_filter_respects_existing_active_mask():
    hits = _hits_for_repeated_pixels()
    mask = np.array([True, True, False, False, True, True, True, True])
    step = RepeatedPixelFilter(max_hits_per_pixel=1, pixel_fields="y,z", round_decimals=3)
    out = step.run({"hits": hits, "active_mask": mask}).data
    assert out["n_repeated_pixel_hits"] == 2


def test_repeated_pixel_filter_missing_field_raises():
    hits = _hits_for_repeated_pixels()
    step = RepeatedPixelFilter(pixel_fields="missing,z")
    with pytest.raises(ValueError, match="missing pixel field"):
        step.run({"hits": hits})


def test_dbscan_respects_active_mask():
    dtype = [("x", "f4"), ("y", "f4"), ("z", "f4"), ("Q", "f4")]
    hits = np.zeros(6, dtype=dtype)
    hits["x"] = [0, 0.1, 0.2, 10, 10.1, 10.2]
    hits["y"] = [0, 0.1, 0.2, 10, 10.1, 10.2]
    hits["z"] = [0, 0.1, 0.2, 10, 10.1, 10.2]
    hits["Q"] = 1
    active_mask = np.array([True, True, True, False, False, False])
    step = DBSCANClusterProducer(eps_cm=1.0, min_samples=2, cluster_min_hits=2, cluster_max_extent_cm=100)
    out = step.run({"hits": hits, "muon_track": None, "active_mask": active_mask}).data
    assert len(out["clusters"]) == 1


def test_default_registry_includes_repeated_pixel_filter():
    reg = default_registry()
    step = reg.create("repeated_pixel_filter")
    assert isinstance(step, RepeatedPixelFilter)


def test_repeated_pixel_yaml_loads():
    cfg = load_pipeline_config("configs/stage2/repeated_pixel_then_dbscan.yaml")
    assert len(cfg["pipeline"]) == 2


def test_pipeline_order_repeated_pixel_then_dbscan_runs():
    hits = _hits_for_repeated_pixels()
    pipeline = Stage2Pipeline([
        RepeatedPixelFilter(max_hits_per_pixel=2, pixel_fields="y,z", round_decimals=3),
        DBSCANClusterProducer(eps_cm=1.0, min_samples=2, cluster_min_hits=2, cluster_max_extent_cm=100),
    ])
    out = pipeline.run({"hits": hits, "muon_track": None})
    assert "clusters" in out
