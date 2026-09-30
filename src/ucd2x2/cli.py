from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Sequence
from urllib.parse import urlsplit


def _optional_float(value):
    return None if value.lower() in ("none", "off") else float(value)


def add_cleaning_arguments(parser):
    # SUPPRESS lets masks retain their saved defaults unless explicitly overridden.
    parser.add_argument("--event-max-hits-per-pixel", dest="event_max_hits", type=int,
                        default=argparse.SUPPRESS, help="Remove ALL hits if count > this; 0 disables (default 3)")
    parser.add_argument("--global-mean-max", type=_optional_float, default=argparse.SUPPRESS,
                        help="Mask total_hits > value*N_events; 'none' disables (default 1)")
    parser.add_argument("--max-event-fraction", type=_optional_float, default=argparse.SUPPRESS,
                        help="Mask pixels present in > this fraction of events (default off)")
    parser.add_argument("--keep-disabled", dest="drop_disabled", action="store_false", default=argparse.SUPPRESS)


def policy_from_args(args, mask=None):
    from ucd2x2.core.hot_pixels import CleaningPolicy
    values = asdict(mask.policy if mask is not None else CleaningPolicy())
    for key in values:
        if hasattr(args, key):
            values[key] = getattr(args, key)
    return CleaningPolicy(**values)


def build_event_display_command(input_h5: str, *, show: bool = True,
                                port: int | None = None, max_hits: int | None = None,
                                hot_mask=None, candidates=None, clean=False, hit_type="prompt",
                                policy_options=None, jupyter=False, hub_url="https://jupyter.nersc.gov",
                                service_prefix=None, event=0) -> list[str]:
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("port must be in 1..65535")
    if event < 0:
        raise ValueError("event index must be nonnegative")
    cleaned = bool(clean or hot_mask or candidates or policy_options or hit_type != "prompt" or event)
    app_name = "clean_panel.py" if cleaned else "app_panel.py"
    app_path = Path(__file__).resolve().parent / "display" / app_name
    cmd = [sys.executable, "-m", "panel", "serve", str(app_path),
           "--address", "127.0.0.1", "--port", str(port or 5006)]
    if show and not jupyter:
        cmd.append("--show")  # Panel has no --no-show argument.
    if jupyter:
        prefix = service_prefix if service_prefix is not None else os.environ.get("JUPYTERHUB_SERVICE_PREFIX")
        if not prefix or not prefix.startswith("/"):
            raise ValueError("Launch --jupyter from a terminal INSIDE the running NERSC Jupyter server")
        origin = urlsplit(hub_url)
        if origin.scheme not in ("http", "https") or not origin.netloc:
            raise ValueError("hub-url must be an http(s) URL")
        root = prefix.rstrip("/") + f"/proxy/{port or 5006}/"
        cmd += ["--allow-websocket-origin", origin.netloc, "--root-path", root]
    cmd += ["--args", "--h5", str(Path(input_h5).expanduser().resolve())]
    if max_hits is not None:
        cmd += ["--max_hits", str(max_hits)]
    if cleaned:
        cmd += ["--hit-type", hit_type, "--event", str(event)]
        if hot_mask:
            cmd += ["--hot-mask", str(Path(hot_mask).expanduser().resolve())]
        if candidates:
            cmd += ["--candidates", str(Path(candidates).expanduser().resolve())]
        cmd += list(policy_options or [])
    return cmd


def _cmd_event_display(args):
    options = []
    for name, flag in (("event_max_hits", "--event-max-hits-per-pixel"),
                       ("global_mean_max", "--global-mean-max"),
                       ("max_event_fraction", "--max-event-fraction")):
        if hasattr(args, name):
            value = getattr(args, name)
            options += [flag, "none" if value is None else str(value)]
    if hasattr(args, "drop_disabled") and not args.drop_disabled:
        options.append("--keep-disabled")
    clean = args.clean or bool(options) or args.hit_type != "prompt" or args.event != 0
    cmd = build_event_display_command(args.input_h5, show=not args.no_show, port=args.port,
        max_hits=args.max_hits, hot_mask=args.hot_mask, candidates=args.candidates,
        clean=clean, hit_type=args.hit_type, policy_options=options,
        jupyter=args.jupyter, hub_url=args.hub_url, event=args.event)
    app = "clean_panel" if clean or args.hot_mask or args.candidates else "app_panel"
    if args.jupyter:
        root = os.environ["JUPYTERHUB_SERVICE_PREFIX"].rstrip("/") + f"/proxy/{args.port}/"
        print(f"Open: {args.hub_url.rstrip('/')}{root}{app}", flush=True)
    else:
        print(f"Open: http://127.0.0.1:{args.port}/{app}", flush=True)
    print("Command:", shlex.join(cmd), flush=True)
    if args.dry_run:
        return 0
    # Retain the legacy app's repository-relative YAML paths, without a user cd.
    repo = Path(__file__).resolve().parents[2]
    cwd = repo if (repo / "configs/stage2").is_dir() else None
    subprocess.run(cmd, check=True, cwd=cwd)
    return 0


def _progress(done, total):
    print(f"  {done:,}/{total:,} events", flush=True)


def _cmd_build(args):
    from ucd2x2.core.hot_pixels import build_hot_mask
    if Path(args.output).exists() and not args.overwrite:
        raise ValueError("Output exists; use --overwrite to replace the derived mask")
    mask = build_hot_mask(args.input_h5, args.output, args.hit_type,
                          policy_from_args(args), args.block_rows, _progress)
    print(json.dumps(mask.summary(), indent=2))
    print("Mask:", Path(args.output).resolve())
    return 0


def _cmd_scan(args):
    from ucd2x2.core.hot_pixels import HotPixelMask
    from ucd2x2.core.event_scan import scan_events
    mask = HotPixelMask.load(args.hot_mask) if args.hot_mask else None
    rows = scan_events(args.input_h5, args.output, mask, policy_from_args(args, mask),
                       args.hit_type, args.block_rows, args.max_events, _progress)
    for row in rows[:10]:
        print(f"event {row['event_index']:8d}  Q={row['total_Q']:12.5g}  hits={row['clean_hits']:7d}")
    print("Candidates:", Path(args.output).resolve())
    return 0


def _video_progress(kind, event_index, done, total):
    if kind == "event_start":
        print(f"Rendering event {event_index}: {total:,} frames", flush=True)
    else:
        print(f"  event {event_index}: {done:,}/{total:,} frames", flush=True)


def _cmd_video(args):
    from ucd2x2.core.hot_pixels import HotPixelMask
    from ucd2x2.display.video_export import export_showcase_video, parse_event_indices

    mask = HotPixelMask.load(args.hot_mask)
    events = parse_event_indices(args.events)
    policy = policy_from_args(args, mask)

    if args.preflight_only:
        from ucd2x2.display.video_export import (
            check_plotly_image_export,
            choose_video_encoder,
            ffmpeg_encoders,
        )
        check_plotly_image_export()
        executable, encoders = ffmpeg_encoders(args.ffmpeg)
        chosen = choose_video_encoder(args.output, encoders, args.encoder)
        print(f"Plotly/Kaleido image export: OK")
        print(f"ffmpeg: {executable}")
        print(f"encoder: {chosen}")
        return 0

    video, sidecar = export_showcase_video(
        args.input_h5,
        args.output,
        event_indices=events,
        mask=mask,
        policy=policy,
        hit_type=args.hit_type,
        fps=args.fps,
        seconds_per_event=args.seconds_per_event,
        hold_seconds=args.hold_seconds,
        start_angle_deg=args.start_angle_deg,
        rotation_degrees=args.rotation_degrees,
        width=args.width,
        height=args.height,
        scale=args.scale,
        point_size=args.point_size,
        max_hits=args.max_hits,
        color_mode=args.color,
        lock_detector_frame=not args.no_lock_detector_frame,
        camera_radius=args.camera_radius,
        camera_height=args.camera_height,
        render_batch=args.render_batch,
        work_dir=args.work_dir,
        keep_frames=args.keep_frames,
        ffmpeg=args.ffmpeg,
        encoder=args.encoder,
        overwrite=args.overwrite,
        progress=_video_progress,
    )
    print(f"Video: {video}")
    print(f"Metadata: {sidecar}")
    return 0


def _cmd_stage2_run(args):
    from ucd2x2.stage2.run_stage2 import run_stage2_file
    summary = run_stage2_file(args.input, args.config, output_summary_path=args.output,
                              max_events=args.max_events)
    if args.output is None:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _build_parser():
    parser = argparse.ArgumentParser(prog="ucd2x2", description="UCD 2x2 analysis tools")
    sub = parser.add_subparsers(dest="command", required=True)
    display = sub.add_parser("event-display", help="Serve the legacy or cleaned Panel browser")
    display.add_argument("input_h5")
    display.add_argument("--no-show", action="store_true")
    display.add_argument("--port", type=int, default=5006)
    display.add_argument("--max-hits", type=int, default=None)
    display.add_argument("--clean", action="store_true", help="Use the cleaning/candidate browser, even without a PKL")
    display.add_argument("--hot-mask")
    display.add_argument("--candidates")
    display.add_argument("--hit-type", choices=("prompt", "final"), default="prompt")
    display.add_argument("--event", type=int, default=0)
    display.add_argument("--jupyter", action="store_true", help="Configure/print the authenticated Jupyter proxy URL")
    display.add_argument("--hub-url", default="https://jupyter.nersc.gov")
    display.add_argument("--dry-run", action="store_true")
    add_cleaning_arguments(display)
    display.set_defaults(func=_cmd_event_display)
    video = sub.add_parser(
        "export-showcase-video",
        help="Render selected cleaned events to a high-resolution MP4/WebM",
    )
    video.add_argument("input_h5")
    video.add_argument("--hot-mask", required=True)
    video.add_argument(
        "--events",
        nargs="+",
        required=True,
        help="Event indices; spaces and/or comma-separated values are accepted",
    )
    video.add_argument("-o", "--output", required=True)
    video.add_argument("--hit-type", choices=("prompt", "final"), default="prompt")
    video.add_argument("--fps", type=int, default=30)
    video.add_argument("--seconds-per-event", type=float, default=4.0)
    video.add_argument("--hold-seconds", type=float, default=0.35)
    video.add_argument("--start-angle-deg", type=float, default=-35.0)
    video.add_argument("--rotation-degrees", type=float, default=180.0)
    video.add_argument("--width", type=int, default=1920)
    video.add_argument("--height", type=int, default=1080)
    video.add_argument("--scale", type=float, default=1.0)
    video.add_argument("--point-size", type=int, default=3)
    video.add_argument("--max-hits", type=int, default=20_000)
    video.add_argument("--color", choices=("Q", "t_drift", "ts_pps"), default="Q")
    video.add_argument("--camera-radius", type=float, default=1.75)
    video.add_argument("--camera-height", type=float, default=0.85)
    video.add_argument("--render-batch", type=int, default=12)
    video.add_argument("--work-dir")
    video.add_argument("--keep-frames", action="store_true")
    video.add_argument("--ffmpeg", default="ffmpeg")
    video.add_argument("--encoder", default="auto")
    video.add_argument("--no-lock-detector-frame", action="store_true")
    video.add_argument("--overwrite", action="store_true")
    video.add_argument("--preflight-only", action="store_true")
    add_cleaning_arguments(video)
    video.set_defaults(func=_cmd_video)

    for name, function in (("build-hot-mask", _cmd_build), ("scan-events", _cmd_scan)):
        p = sub.add_parser(name)
        p.add_argument("input_h5")
        p.add_argument("-o", "--output", required=True)
        p.add_argument("--hit-type", choices=("prompt", "final"), default="prompt")
        p.add_argument("--block-rows", type=int, default=250_000)
        add_cleaning_arguments(p)
        if name == "build-hot-mask":
            p.add_argument("--overwrite", action="store_true")
        else:
            p.add_argument("--hot-mask")
            p.add_argument("--max-events", type=int)
        p.set_defaults(func=function)
    p = sub.add_parser("stage2-run")
    p.add_argument("--input", required=True); p.add_argument("--config", required=True)
    p.add_argument("--output"); p.add_argument("--max-events", type=int, default=None)
    p.set_defaults(func=_cmd_stage2_run)
    return parser


def main(argv: Sequence[str] | None = None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, OSError, KeyError, RuntimeError) as exc:
        parser.error(str(exc))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
