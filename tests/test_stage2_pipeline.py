import numpy as np

from twobytwo_display.stage2.cuts import DBSCANClusterProducer
from twobytwo_display.stage2.pipeline import CutStep, Stage2Pipeline, StepResult


def _make_synthetic_hits():
    dtype = [("x", "f4"), ("y", "f4"), ("z", "f4"), ("Q", "f4")]
    a = np.zeros(12, dtype=dtype)
    a["x"] = np.linspace(0.0, 0.8, len(a))
    a["y"] = np.linspace(0.0, 0.8, len(a))
    a["z"] = np.linspace(0.0, 0.8, len(a))
    a["Q"] = 1.0

    b = np.zeros(12, dtype=dtype)
    b["x"] = np.linspace(20.0, 20.8, len(b))
    b["y"] = np.linspace(20.0, 20.8, len(b))
    b["z"] = np.linspace(20.0, 20.8, len(b))
    b["Q"] = 2.0

    return np.concatenate([a, b])


def test_dbscan_cluster_producer_runs_on_synthetic_hits():
    hits = _make_synthetic_hits()
    step = DBSCANClusterProducer(
        eps_cm=2.0,
        min_samples=3,
        cluster_min_hits=3,
        cluster_max_extent_cm=10_000.0,
    )
    out = step.run({"hits": hits, "muon_track": None}).data
    assert "clusters" in out
    assert isinstance(out["clusters"], list)
    assert len(out["clusters"]) >= 1


class _RecordStep(CutStep):
    def __init__(self, name, order):
        super().__init__()
        self.name = name
        self.order = order

    def run(self, context):
        order = list(context.get("order", []))
        order.append(self.name)
        return StepResult({"order": order})


def test_stage2_pipeline_runs_steps_in_order():
    pipeline = Stage2Pipeline([
        _RecordStep("first", []),
        _RecordStep("second", []),
        _RecordStep("third", []),
    ])
    out = pipeline.run({})
    assert out["order"] == ["first", "second", "third"]
