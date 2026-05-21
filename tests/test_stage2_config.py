from pathlib import Path

import pytest

from twobytwo_display.stage2.config import (
    default_registry,
    dump_pipeline_config,
    load_pipeline,
    pipeline_from_dict,
    pipeline_to_dict,
)


def _valid_config_dict():
    return {
        "pipeline": [
            {
                "name": "dbscan_cluster_producer",
                "enabled": True,
                "params": {
                    "eps_cm": 1.5,
                    "min_samples": 10,
                    "cluster_min_hits": 20,
                    "cluster_max_extent_cm": 8.0,
                },
            }
        ]
    }


def test_pipeline_from_dict_preserves_order_and_skips_disabled():
    cfg = {
        "pipeline": [
            {"name": "dbscan_cluster_producer", "enabled": True, "params": {"eps_cm": 1.5}},
            {"name": "dbscan_cluster_producer", "enabled": False, "params": {"eps_cm": 2.0}},
            {"name": "dbscan_cluster_producer", "enabled": True, "params": {"eps_cm": 3.0}},
        ]
    }
    pipeline = pipeline_from_dict(cfg, registry=default_registry())
    assert len(pipeline.steps) == 2
    assert pipeline.steps[0].params["eps_cm"] == 1.5
    assert pipeline.steps[1].params["eps_cm"] == 3.0


def test_unknown_step_raises_clear_error():
    cfg = {"pipeline": [{"name": "not_registered", "enabled": True, "params": {}}]}
    with pytest.raises(ValueError, match="Unknown stage2 step 'not_registered'"):
        pipeline_from_dict(cfg, registry=default_registry())


def test_round_trip_dict_and_yaml(tmp_path: Path):
    cfg = _valid_config_dict()
    normalized = pipeline_to_dict(cfg)
    dumped = dump_pipeline_config(normalized)
    path = tmp_path / "stage2.yaml"
    path.write_text(dumped)

    pipeline = load_pipeline(path, registry=default_registry())
    assert len(pipeline.steps) == 1
    assert pipeline.steps[0].name == "dbscan_cluster_producer"
    assert pipeline.steps[0].params["cluster_max_extent_cm"] == 8.0
