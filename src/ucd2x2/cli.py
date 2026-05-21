from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Sequence

from ucd2x2.stage2.run_stage2 import run_stage2_file


def build_event_display_command(input_h5: str, *, show: bool = True, port: int | None = None, max_hits: int | None = None) -> list[str]:
    app_path = Path(__file__).resolve().parent / "display" / "app_panel.py"
    cmd = ["panel", "serve", str(app_path)]
    cmd.append("--show" if show else "--no-show")
    if port is not None:
        cmd.extend(["--port", str(port)])
    cmd.extend(["--args", "--h5", str(input_h5)])
    if max_hits is not None:
        cmd.extend(["--max-hits", str(max_hits)])
    return cmd


def _cmd_event_display(args: argparse.Namespace) -> int:
    cmd = build_event_display_command(
        args.input_h5,
        show=not args.no_show,
        port=args.port,
        max_hits=args.max_hits,
    )
    subprocess.run(cmd, check=True)
    return 0


def _cmd_stage2_run(args: argparse.Namespace) -> int:
    summary = run_stage2_file(
        args.input,
        args.config,
        output_summary_path=args.output,
        max_events=args.max_events,
    )
    if args.output is None:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ucd2x2", description="UCD 2x2 analysis command-line tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_display = subparsers.add_parser("event-display", help="Launch the Panel event display")
    p_display.add_argument("input_h5", help="Input HDF5 file")
    p_display.add_argument("--no-show", action="store_true", help="Start server without opening a browser")
    p_display.add_argument("--port", type=int, default=None, help="Optional port for panel serve")
    p_display.add_argument("--max-hits", type=int, default=None, help="Optional max hits passed to app_panel")
    p_display.set_defaults(func=_cmd_event_display)

    p_stage2 = subparsers.add_parser("stage2-run", help="Run Stage 2 pipeline over one HDF5 file")
    p_stage2.add_argument("--input", required=True, help="Input HDF5 file")
    p_stage2.add_argument("--config", required=True, help="Stage 2 YAML config path")
    p_stage2.add_argument("--output", default=None, help="Optional JSON summary output path")
    p_stage2.add_argument("--max-events", type=int, default=None, help="Optional max number of events to process")
    p_stage2.set_defaults(func=_cmd_stage2_run)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
