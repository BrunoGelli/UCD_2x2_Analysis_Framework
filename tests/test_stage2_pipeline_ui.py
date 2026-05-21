from twobytwo_display.stage2.config import default_registry, load_pipeline_config
from twobytwo_display.stage2.pipeline_ui import add_step, config_to_ui_steps, move_step, remove_step, ui_steps_to_config, widgets_for_step


def test_pipeline_ui_round_trip_preserves_order_enabled_params():
    cfg = load_pipeline_config("configs/stage2/repeated_pixel_then_dbscan.yaml")
    steps = config_to_ui_steps(cfg, registry=default_registry())
    out = ui_steps_to_config(steps)
    assert [s["name"] for s in out["pipeline"]] == [s["name"] for s in cfg["pipeline"]]
    assert [s["enabled"] for s in out["pipeline"]] == [s["enabled"] for s in cfg["pipeline"]]
    assert out["pipeline"][0]["params"]["max_hits_per_pixel"] == cfg["pipeline"][0]["params"]["max_hits_per_pixel"]


def test_add_remove_move_step_state():
    steps = []
    steps = add_step(steps, "repeated_pixel_filter", registry=default_registry())
    steps = add_step(steps, "dbscan_cluster_producer", registry=default_registry())
    steps = move_step(steps, 1, -1)
    assert steps[0].name == "dbscan_cluster_producer"
    steps = remove_step(steps, 1)
    assert len(steps) == 1


def test_widgets_for_both_steps():
    w1 = widgets_for_step("repeated_pixel_filter", registry=default_registry())
    w2 = widgets_for_step("dbscan_cluster_producer", registry=default_registry())
    assert "max_hits_per_pixel" in w1
    assert "eps_cm" in w2
