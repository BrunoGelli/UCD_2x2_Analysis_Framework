import json

from twobytwo_display.stage2.run_stage2 import run_stage2_file


def test_run_stage2_file_summary_on_fixture():
    summary = run_stage2_file(
        "tests/sample_data.hdf5",
        "configs/stage2/dbscan_default.yaml",
    )
    assert summary["n_events_total"] > 0
    assert summary["n_events_processed"] > 0
    assert "total_clusters" in summary


def test_run_stage2_file_writes_json_and_max_events(tmp_path):
    out = tmp_path / "summary.json"
    summary = run_stage2_file(
        "tests/sample_data.hdf5",
        "configs/stage2/dbscan_default.yaml",
        output_summary_path=out,
        max_events=2,
    )
    assert out.exists()
    loaded = json.loads(out.read_text())
    assert loaded["n_events_processed"] <= 2
    assert loaded["n_events_processed"] == summary["n_events_processed"]
