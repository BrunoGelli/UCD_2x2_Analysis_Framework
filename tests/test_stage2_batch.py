import json
import subprocess
import sys

from ucd2x2.stage2.run_stage2 import run_stage2_file


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


def test_run_stage2_module_does_not_emit_runpy_warning(tmp_path):
    out = tmp_path / "summary.json"
    cmd = [
        sys.executable,
        "-m",
        "ucd2x2.stage2.run_stage2",
        "--input",
        "tests/sample_data.hdf5",
        "--config",
        "configs/stage2/dbscan_default.yaml",
        "--output",
        str(out),
        "--max-events",
        "1",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert "found in sys.modules" not in proc.stderr
    assert out.exists()


def test_run_stage2_file_with_repeated_pixel_pipeline():
    summary = run_stage2_file(
        "tests/sample_data.hdf5",
        "configs/stage2/repeated_pixel_then_dbscan.yaml",
        max_events=2,
    )
    assert "total_repeated_pixel_hits" in summary
    assert "total_repeated_pixels" in summary
