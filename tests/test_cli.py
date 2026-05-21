import json
import subprocess
import sys

from ucd2x2.cli import build_event_display_command


def test_cli_help_runs_successfully():
    proc = subprocess.run([sys.executable, "-m", "ucd2x2.cli", "--help"], capture_output=True, text=True, check=True)
    assert "event-display" in proc.stdout
    assert "stage2-run" in proc.stdout


def test_stage2_run_via_cli_writes_summary_json(tmp_path):
    out = tmp_path / "stage2_summary.json"
    cmd = [
        sys.executable,
        "-m",
        "ucd2x2.cli",
        "stage2-run",
        "--input",
        "tests/sample_data.hdf5",
        "--config",
        "configs/stage2/repeated_pixel_then_dbscan.yaml",
        "--output",
        str(out),
        "--max-events",
        "2",
    ]
    subprocess.run(cmd, check=True)
    assert out.exists()
    payload = json.loads(out.read_text())
    assert payload["n_events_processed"] <= 2
    assert "total_clusters" in payload


def test_build_event_display_command_defaults():
    cmd = build_event_display_command("tests/sample_data.hdf5")
    assert cmd[:3] == ["panel", "serve", cmd[2]]
    assert cmd[3] == "--show"
    assert cmd[-3:] == ["--args", "--h5", "tests/sample_data.hdf5"]


def test_build_event_display_command_optional_args():
    cmd = build_event_display_command(
        "tests/sample_data.hdf5",
        show=False,
        port=5007,
        max_hits=120,
    )
    assert "--no-show" in cmd
    assert "--show" not in cmd
    assert ["--port", "5007"] == cmd[cmd.index("--port") : cmd.index("--port") + 2]
    assert ["--max-hits", "120"] == cmd[cmd.index("--max-hits") : cmd.index("--max-hits") + 2]
