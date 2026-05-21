from pathlib import Path

from twobytwo_display.stage2.config import dump_pipeline_config, load_pipeline_config
from twobytwo_display.stage2.ui_config import (
    apply_stage2_config_to_dbscan_values,
    build_stage2_config_from_dbscan_values,
)


def test_build_stage2_config_from_dbscan_values():
    values = {
        "show_clusters": True,
        "eps_cm": 2.5,
        "min_samples": 7,
        "cluster_min_hits": 12,
        "cluster_max_extent_cm": 9.5,
    }
    cfg = build_stage2_config_from_dbscan_values(values)
    step = cfg["pipeline"][0]
    assert step["name"] == "dbscan_cluster_producer"
    assert step["enabled"] is True
    assert step["params"]["eps_cm"] == 2.5


def test_apply_stage2_config_to_dbscan_values_ignores_unknown_steps():
    values = {"show_clusters": False, "eps_cm": 1.5, "min_samples": 10, "cluster_min_hits": 20, "cluster_max_extent_cm": 8.0}
    cfg = {
        "pipeline": [
            {"name": "unknown", "enabled": True, "params": {"eps_cm": 99}},
            {"name": "dbscan_cluster_producer", "enabled": True, "params": {"eps_cm": 3.0, "min_samples": 4, "cluster_min_hits": 5, "cluster_max_extent_cm": 6.0}},
        ]
    }
    out = apply_stage2_config_to_dbscan_values(cfg, values)
    assert out["show_clusters"] is True
    assert out["eps_cm"] == 3.0
    assert out["min_samples"] == 4


def test_save_then_load_preserves_dbscan_parameters(tmp_path: Path):
    values = {"show_clusters": True, "eps_cm": 1.8, "min_samples": 6, "cluster_min_hits": 9, "cluster_max_extent_cm": 7.0}
    cfg = build_stage2_config_from_dbscan_values(values)
    p = tmp_path / "cfg.yaml"
    p.write_text(dump_pipeline_config(cfg))
    loaded = load_pipeline_config(p)

    reset = {"show_clusters": False, "eps_cm": 0.0, "min_samples": 0, "cluster_min_hits": 0, "cluster_max_extent_cm": 0.0}
    apply_stage2_config_to_dbscan_values(loaded, reset)
    assert reset == values


def test_default_yaml_loads():
    cfg = load_pipeline_config("configs/stage2/dbscan_default.yaml")
    assert cfg["pipeline"][0]["name"] == "dbscan_cluster_producer"
