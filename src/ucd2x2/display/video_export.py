"""Render selected cleaned FLOW events to high-resolution video frames."""
from __future__ import annotations

from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

from ucd2x2.core.event_scan import event_summary
from ucd2x2.core.hot_pixels import EventCleaner, EventHitReader
from ucd2x2.display.viz import (
    apply_detector_frame,
    camera_for_angle,
    make_plotly_3d,
)


def parse_event_indices(values):
    """Accept --events 1 2 3, --events 1,2,3, or a mixture."""
    tokens = []
    for value in values:
        tokens.extend(str(value).replace(",", " ").split())
    if not tokens:
        raise ValueError("At least one event index is required")
    result, seen = [], set()
    for token in tokens:
        try:
            index = int(token)
        except ValueError as exc:
            raise ValueError(f"Invalid event index: {token!r}") from exc
        if index < 0:
            raise ValueError("Event indices must be nonnegative")
        if index not in seen:
            seen.add(index)
            result.append(index)
    return result


def ffmpeg_encoders(ffmpeg="ffmpeg"):
    """Return encoder names advertised by ffmpeg -encoders."""
    executable = shutil.which(ffmpeg) if os.path.sep not in ffmpeg else ffmpeg
    if not executable or not Path(executable).exists():
        raise ValueError(
            f"ffmpeg executable not found: {ffmpeg!r}. "
            "Install ffmpeg in the active environment or pass --ffmpeg."
        )
    proc = subprocess.run(
        [executable, "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
    )
    if proc.returncode:
        raise ValueError(
            f"Could not inspect ffmpeg encoders ({executable}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    encoders = set()
    for line in (proc.stdout + "\n" + proc.stderr).splitlines():
        match = re.match(r"^\s*[A-Z\.]{6}\s+(\S+)", line)
        if match:
            encoders.add(match.group(1))
    return str(executable), encoders


def choose_video_encoder(output, encoders, requested="auto"):
    """Choose a Slack/browser-friendly codec from the output suffix."""
    output = Path(output)
    suffix = output.suffix.lower()
    if suffix not in (".mp4", ".webm"):
        raise ValueError("Video output must end in .mp4 or .webm")

    if requested != "auto":
        if requested not in encoders:
            raise ValueError(f"Requested ffmpeg encoder {requested!r} is unavailable")
        return requested

    if suffix == ".mp4":
        for encoder in ("libx264", "libopenh264"):
            if encoder in encoders:
                return encoder
        raise ValueError(
            "This ffmpeg cannot encode a Slack-friendly H.264 MP4: neither "
            "libx264 nor libopenh264 is available. The NERSC system ffmpeg often "
            "has this limitation. Install a conda-forge ffmpeg in the active "
            "environment (for example: conda install -c conda-forge ffmpeg), "
            "then rerun. As an immediate fallback, .webm can use libvpx-vp9 "
            "when that encoder is available."
        )

    if "libvpx-vp9" in encoders:
        return "libvpx-vp9"
    raise ValueError("This ffmpeg does not provide libvpx-vp9 for WebM output")


def check_plotly_image_export():
    """Fail early if Kaleido/Chrome cannot render Plotly static images."""
    probe = go.Figure(go.Scatter(x=[0, 1], y=[0, 1]))
    try:
        pio.to_image(probe, format="png", width=96, height=64, scale=1)
    except Exception as exc:
        raise ValueError(
            "Plotly static image export failed. Kaleido v1 requires a compatible "
            "Chrome/Chromium executable. Verify with 'plotly_get_chrome' (or set "
            "BROWSER_PATH to an existing compatible browser). Original error: "
            f"{exc}"
        ) from exc


def _charge_range(fig, hits):
    positive = hits["Q"][np.isfinite(hits["Q"]) & (hits["Q"] > 0)]
    values = np.log10(positive) if len(positive) else np.array([0.0, 1.0])
    lo, hi = float(values.min()), float(values.max())
    if hi <= lo:
        lo, hi = lo - 0.5, hi + 0.5
    for trace in fig.data:
        marker = getattr(trace, "marker", None)
        if trace.type == "scatter3d" and marker is not None and marker.color is not None:
            marker.cauto = False
            marker.cmin, marker.cmax = lo, hi


def _subsample(hits, max_hits, seed):
    if len(hits) <= max_hits:
        return hits
    selected = np.sort(
        np.random.default_rng(seed).choice(len(hits), int(max_hits), replace=False)
    )
    return hits[selected]


def build_video_figure(
    reader,
    cleaner,
    index,
    *,
    color_mode="Q",
    point_size=3,
    max_hits=20_000,
    lock_detector_frame=True,
):
    """Build one cleaned 3D figure using the same source/cleaning path as Panel."""
    raw = reader.get(index)
    keep, report = cleaner.apply(raw)
    hits = raw[keep]
    plotted = _subsample(hits, max_hits, index)

    fig = make_plotly_3d(
        plotted,
        color_mode=color_mode,
        max_hits=max(1, len(plotted)),
        point_size=point_size,
        show_boxes=True,
    )
    if color_mode == "Q":
        _charge_range(fig, plotted)
    if lock_detector_frame:
        apply_detector_frame(fig, None, padding_cm=2.0)

    summary = event_summary(hits)
    event_id = reader.event_id(index)
    fig.update_layout(
        title=dict(
            text=(
                f"2×2 ND-LAr — Event {index}"
                f"<br><sup>Event ID {event_id} · "
                f"{len(hits):,} cleaned hits · ΣQ {summary['total_Q']:.4g}</sup>"
            ),
            x=0.5,
            xanchor="center",
            y=0.97,
            yanchor="top",
        ),
        margin=dict(l=0, r=105, t=85, b=0),
        paper_bgcolor="white",
        uirevision=None,
    )
    metadata = {
        "event_index": int(index),
        "event_id": int(event_id),
        "raw_hits": int(len(raw)),
        "clean_hits": int(len(hits)),
        "plotted_hits": int(len(plotted)),
        "cleaning_report": dict(report),
        "event_summary": dict(summary),
    }
    return fig, metadata


def _camera_angles(
    *,
    fps,
    seconds_per_event,
    hold_seconds,
    start_angle_deg,
    rotation_degrees,
):
    motion_frames = max(2, int(round(float(fps) * float(seconds_per_event))))
    hold_frames = max(0, int(round(float(fps) * float(hold_seconds))))
    start = math.radians(float(start_angle_deg))
    stop = start + math.radians(float(rotation_degrees))
    motion = np.linspace(start, stop, motion_frames, endpoint=True)
    if hold_frames:
        motion = np.concatenate(
            [
                np.full(hold_frames, motion[0], dtype=float),
                motion,
                np.full(hold_frames, motion[-1], dtype=float),
            ]
        )
    return motion


def _write_figure_batch(figures, files, *, width, height, scale):
    """Use Plotly/Kaleido's multi-image path when available; fall back safely."""
    if hasattr(pio, "write_images"):
        pio.write_images(
            fig=list(figures),
            file=list(files),
            format="png",
            width=int(width),
            height=int(height),
            scale=float(scale),
            validate=True,
        )
        return
    for fig, path in zip(figures, files):
        pio.write_image(
            fig,
            path,
            format="png",
            width=int(width),
            height=int(height),
            scale=float(scale),
            validate=True,
        )


def render_event_frames(
    base_figure,
    angles,
    *,
    frame_dir,
    first_frame,
    width,
    height,
    scale,
    camera_radius,
    camera_height,
    render_batch,
    progress=None,
):
    frame_dir = Path(frame_dir)
    frame_dir.mkdir(parents=True, exist_ok=True)
    n_total = len(angles)
    written = 0

    for start in range(0, n_total, int(render_batch)):
        batch_angles = angles[start : start + int(render_batch)]
        figures, paths = [], []
        for offset, angle in enumerate(batch_angles):
            fig = go.Figure(base_figure)
            fig.update_layout(
                scene_camera=camera_for_angle(
                    float(angle),
                    radius=float(camera_radius),
                    height=float(camera_height),
                )
            )
            frame_number = first_frame + start + offset
            path = frame_dir / f"frame_{frame_number:06d}.png"
            figures.append(fig)
            paths.append(path)
        _write_figure_batch(
            figures,
            paths,
            width=width,
            height=height,
            scale=scale,
        )
        written += len(paths)
        if progress is not None:
            progress(written, n_total)
    return first_frame + n_total


def assemble_video(
    frame_dir,
    output,
    *,
    fps,
    ffmpeg="ffmpeg",
    encoder="auto",
    overwrite=False,
):
    output = Path(output).expanduser().resolve()
    if output.exists() and not overwrite:
        raise ValueError(f"Output already exists: {output}. Use --overwrite to replace it")
    output.parent.mkdir(parents=True, exist_ok=True)

    executable, encoders = ffmpeg_encoders(ffmpeg)
    chosen = choose_video_encoder(output, encoders, encoder)
    pattern = str(Path(frame_dir) / "frame_%06d.png")

    cmd = [
        executable,
        "-hide_banner",
        "-loglevel", "warning",
        "-y" if overwrite else "-n",
        "-framerate", str(int(fps)),
        "-start_number", "0",
        "-i", pattern,
        "-an",
    ]
    if chosen in ("libx264", "libopenh264"):
        cmd += ["-c:v", chosen]
        if chosen == "libx264":
            cmd += ["-preset", "medium", "-crf", "18"]
        cmd += ["-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    elif chosen == "libvpx-vp9":
        cmd += ["-c:v", chosen, "-b:v", "0", "-crf", "28", "-pix_fmt", "yuv420p"]
    else:
        cmd += ["-c:v", chosen]

    cmd.append(str(output))
    proc = subprocess.run(cmd)
    if proc.returncode:
        raise ValueError(f"ffmpeg failed with exit status {proc.returncode}")
    return output, chosen, cmd


def export_showcase_video(
    input_h5,
    output,
    *,
    event_indices,
    mask,
    policy,
    hit_type="prompt",
    fps=30,
    seconds_per_event=4.0,
    hold_seconds=0.35,
    start_angle_deg=-35.0,
    rotation_degrees=180.0,
    width=1920,
    height=1080,
    scale=1.0,
    point_size=3,
    max_hits=20_000,
    color_mode="Q",
    lock_detector_frame=True,
    camera_radius=1.75,
    camera_height=0.85,
    render_batch=12,
    work_dir=None,
    keep_frames=False,
    ffmpeg="ffmpeg",
    encoder="auto",
    overwrite=False,
    progress=None,
):
    events = parse_event_indices(event_indices)
    if fps < 1 or fps > 120:
        raise ValueError("fps must be in 1..120")
    if seconds_per_event <= 0 or hold_seconds < 0:
        raise ValueError("seconds-per-event must be >0 and hold-seconds must be >=0")
    if width < 320 or height < 240 or scale <= 0:
        raise ValueError("Invalid output dimensions or scale")
    if max_hits < 1 or render_batch < 1:
        raise ValueError("max-hits and render-batch must be positive")

    # Preflight before reading/rendering multi-GB data. Check the final video
    # encoder first because the NERSC system ffmpeg may lack H.264 support.
    executable, encoders = ffmpeg_encoders(ffmpeg)
    chosen = choose_video_encoder(output, encoders, encoder)
    check_plotly_image_export()

    temp = None
    if work_dir is not None:
        frames = Path(work_dir).expanduser().resolve()
        frames.mkdir(parents=True, exist_ok=True)
    elif keep_frames:
        frames = Path(output).expanduser().resolve().parent / (Path(output).stem + "_frames")
        frames.mkdir(parents=True, exist_ok=True)
    else:
        scratch = os.environ.get("PSCRATCH")
        parent = Path(scratch) if scratch and Path(scratch).is_dir() else Path(output).expanduser().resolve().parent
        temp = tempfile.TemporaryDirectory(prefix="ucd2x2-video-", dir=parent)
        frames = Path(temp.name)

    for stale in frames.glob("frame_*.png"):
        stale.unlink()

    cleaner = EventCleaner(mask, policy)
    rows = []
    frame_counter = 0
    angles = _camera_angles(
        fps=fps,
        seconds_per_event=seconds_per_event,
        hold_seconds=hold_seconds,
        start_angle_deg=start_angle_deg,
        rotation_degrees=rotation_degrees,
    )

    try:
        with EventHitReader(input_h5, hit_type) as reader:
            if mask is not None:
                mask.validate(reader)
            for index in events:
                if not 0 <= index < len(reader):
                    raise ValueError(
                        f"Event index {index} outside valid range 0..{len(reader)-1}"
                    )
                fig, metadata = build_video_figure(
                    reader,
                    cleaner,
                    index,
                    color_mode=color_mode,
                    point_size=point_size,
                    max_hits=max_hits,
                    lock_detector_frame=lock_detector_frame,
                )
                if progress is not None:
                    progress("event_start", index, 0, len(angles))
                def frame_progress(done, total, event_index=index):
                    if progress is not None:
                        progress("frames", event_index, done, total)
                frame_counter = render_event_frames(
                    fig,
                    angles,
                    frame_dir=frames,
                    first_frame=frame_counter,
                    width=width,
                    height=height,
                    scale=scale,
                    camera_radius=camera_radius,
                    camera_height=camera_height,
                    render_batch=render_batch,
                    progress=frame_progress,
                )
                rows.append(metadata)
            reader.check_unchanged()

        video, _, cmd = assemble_video(
            frames,
            output,
            fps=fps,
            ffmpeg=executable,
            encoder=chosen,
            overwrite=overwrite,
        )
        sidecar = Path(str(video) + ".json")
        sidecar.write_text(
            json.dumps(
                {
                    "schema": "ucd2x2.showcase-video.v1",
                    "source": str(Path(input_h5).expanduser().resolve()),
                    "hit_type": hit_type,
                    "events": rows,
                    "policy": asdict(policy),
                    "render": {
                        "fps": fps,
                        "seconds_per_event": seconds_per_event,
                        "hold_seconds": hold_seconds,
                        "start_angle_deg": start_angle_deg,
                        "rotation_degrees": rotation_degrees,
                        "width": width,
                        "height": height,
                        "scale": scale,
                        "point_size": point_size,
                        "max_hits": max_hits,
                        "color_mode": color_mode,
                        "camera_radius": camera_radius,
                        "camera_height": camera_height,
                        "n_frames": frame_counter,
                    },
                    "ffmpeg_encoder": chosen,
                    "ffmpeg_command": cmd,
                    "frames_kept": bool(keep_frames or work_dir),
                    "frame_directory": str(frames) if (keep_frames or work_dir) else None,
                },
                indent=2,
                default=str,
            )
            + "\n"
        )
        return video, sidecar
    finally:
        if temp is not None:
            temp.cleanup()
