"""Standalone multi-event HTML showcase export."""
from __future__ import annotations

from html import escape
import json
import os
from pathlib import Path
import tempfile

import numpy as np
from plotly.offline import get_plotlyjs
from plotly.utils import PlotlyJSONEncoder


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            delete=False, suffix=".html.tmp",
        ) as stream:
            name = stream.name
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def _freeze_marker_colors(fig):
    for trace in fig.data:
        marker = getattr(trace, "marker", None)
        if marker is None:
            continue
        color = getattr(marker, "color", None)
        if color is None or isinstance(color, str):
            continue
        try:
            values = np.asarray(color)
        except Exception:
            continue
        if values.ndim != 1 or values.size == 0:
            continue
        if not np.issubdtype(values.dtype, np.number):
            continue
        marker.color = values.astype(float).tolist()
        if marker.cmin is not None and marker.cmax is not None:
            marker.cauto = False
    return fig


def _figure_payload(fig):
    _freeze_marker_colors(fig)
    payload = fig.to_plotly_json()
    return {
        "data": payload.get("data", []),
        "layout": payload.get("layout", {}),
    }


def export_showcase_html(
    output_path,
    *,
    title,
    subtitle="",
    events,
    seconds_per_rotation=18.0,
):
    """Write a compact multi-event showcase.

    Each event dict contains event_index, event_id, fig3d, fig2d and metadata.
    Only the visible event is rotated; hidden WebGL scenes remain paused.
    """
    output = Path(output_path).expanduser().resolve()
    event_list = list(events)
    if not event_list:
        raise ValueError("showcase requires at least one event")

    seconds = max(3.0, float(seconds_per_rotation))
    safe_title = escape(str(title))
    safe_subtitle = escape(str(subtitle or ""))

    tabs, panels, scripts, rotators = [], [], [], []
    config_json = json.dumps({
        "responsive": True,
        "displaylogo": False,
        "scrollZoom": True,
    })

    for position, event in enumerate(event_list):
        event_index = int(event["event_index"])
        event_id = event.get("event_id", event_index)
        prefix = f"showcase-event-{position}"
        div3d = f"{prefix}-3d"
        div2d = f"{prefix}-2d"
        section_id = f"{prefix}-panel"
        active = " active" if position == 0 else ""

        metadata = dict(event.get("metadata", {}))
        metadata_json = escape(json.dumps(
            metadata, indent=2, sort_keys=True, default=str
        ))
        summary = metadata.get("event_summary", {}) or {}
        report = metadata.get("cleaning_report", {}) or {}
        quick = []
        if summary.get("total_Q") is not None:
            quick.append(f"Œ£Q {float(summary['total_Q']):.4g}")
        if report.get("clean_hits") is not None:
            quick.append(f"{int(report['clean_hits']):,} hits")
        if summary.get("n_unique_pixels") is not None:
            quick.append(f"{int(summary['n_unique_pixels']):,} pixels")
        quick_text = " ¬∑ ".join(quick)

        tabs.append(
            f'<button class="event-tab{active}" '
            f'onclick="showEvent({position})">Event {event_index}</button>'
        )

        fig3d_json = json.dumps(
            _figure_payload(event["fig3d"]),
            cls=PlotlyJSONEncoder,
            separators=(",", ":"),
        )
        fig2d_json = json.dumps(
            _figure_payload(event["fig2d"]),
            cls=PlotlyJSONEncoder,
            separators=(",", ":"),
        )
        scripts.append(
            f'const f3_{position}={fig3d_json};'
            f'const f2_{position}={fig2d_json};'
            f'Plotly.newPlot("{div3d}",f3_{position}.data,f3_{position}.layout,plotConfig);'
            f'Plotly.newPlot("{div2d}",f2_{position}.data,f2_{position}.layout,plotConfig);'
        )
        rotators.append(
            f'rotators[{position}]=makeRotator("{div3d}",{seconds});'
        )

        panels.append(f"""
<section id="{section_id}" class="event-panel{active}">
  <div class="event-heading">
    <div>
      <h2>Event {event_index}</h2>
      <div class="event-id">Event ID {escape(str(event_id))}</div>
    </div>
    <div class="quick-metadata">{escape(quick_text)}</div>
  </div>

  <div class="viewer-card">
    <div class="viewer-controls">
      <button onclick="rotators[{position}].play()">‚ñ∂ Rotate</button>
      <button onclick="rotators[{position}].pause()">‚è∏ Pause</button>
    </div>
    <div id="{div3d}" class="plot plot-3d"></div>
  </div>

  <div class="projection-heading">Orthogonal projections</div>
  <div class="viewer-card">
    <div id="{div2d}" class="plot plot-2d"></div>
  </div>

  <details class="metadata">
    <summary>Technical details</summary>
    <pre>{metadata_json}</pre>
  </details>
</section>
""")

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
<style>
:root {{
  color-scheme: light;
  --ink:#17202a; --muted:#68717d; --line:#dfe4ea;
  --paper:#fff; --page:#f4f6f8; --accent:#294c73;
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--page); color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
}}
header,.event-tabs,main,footer {{ max-width:1420px; margin:0 auto; }}
header {{ padding:30px 28px 18px; }}
h1 {{
  margin:0 0 7px; font-size:clamp(1.65rem,3vw,2.35rem);
  font-weight:650; letter-spacing:-0.02em;
}}
.subtitle {{ color:var(--muted); line-height:1.45; }}
.event-tabs {{
  padding:0 28px 18px; display:flex; flex-wrap:wrap; gap:8px;
}}
button {{ font:inherit; }}
.event-tab,.viewer-controls button {{
  border:1px solid var(--line); background:var(--paper); color:var(--ink);
  border-radius:7px; padding:8px 12px; cursor:pointer;
}}
.event-tab.active {{ background:var(--accent); border-color:var(--accent); color:#fff; }}
main {{ padding:0 28px 44px; }}
.event-panel {{ display:none; }}
.event-panel.active {{ display:block; }}
.event-heading {{
  display:flex; justify-content:space-between; align-items:end;
  gap:16px; margin:4px 0 12px;
}}
.event-heading h2 {{ margin:0; font-size:1.4rem; }}
.event-id,.quick-metadata {{ color:var(--muted); font-size:.9rem; }}
.viewer-card {{
  position:relative; background:var(--paper); border:1px solid var(--line);
  border-radius:10px; overflow:hidden; margin-bottom:18px;
}}
.viewer-controls {{
  position:absolute; z-index:10; top:10px; left:10px; display:flex; gap:6px;
}}
.viewer-controls button {{ background:rgba(255,255,255,.94); }}
.plot {{ width:100%; }}
.plot-3d {{ min-height:690px; }}
.plot-2d {{ min-height:760px; }}
.projection-heading {{ margin:20px 0 8px; font-weight:600; }}
.metadata {{
  margin-top:18px; background:var(--paper); border:1px solid var(--line);
  border-radius:8px; padding:10px 14px;
}}
.metadata summary {{ cursor:pointer; color:var(--muted); }}
.metadata pre {{ white-space:pre-wrap; overflow-wrap:anywhere; font-size:.78rem; }}
footer {{ padding:0 28px 32px; color:var(--muted); font-size:.78rem; }}
@media(max-width:760px) {{
  header,.event-tabs,main,footer {{ padding-left:14px; padding-right:14px; }}
  .event-heading {{ align-items:start; flex-direction:column; }}
  .plot-3d {{ min-height:540px; }}
}}
</style>
<script>{get_plotlyjs()}</script>
</head>
<body>
<header>
  <h1>{safe_title}</h1>
  <div class="subtitle">{safe_subtitle}</div>
</header>
<nav class="event-tabs">{"".join(tabs)}</nav>
<main>{"".join(panels)}</main>
<footer>
Interactive charge-readout event displays from reconstructed FLOW data.
Technical details are intentionally collapsed by default.
</footer>

<script>
const plotConfig={config_json};
const rotators={{}};
let activeEvent=0;

function makeRotator(divId,secondsPerTurn) {{
  let running=false, angle=0, last=performance.now(), lastDraw=0;
  const radius=1.75, height=.85, minFrameMs=33;

  function frame(now) {{
    if(!running) return;
    const dt=Math.max(0,now-last)/1000;
    last=now;
    angle=(angle+2*Math.PI*dt/secondsPerTurn)%(2*Math.PI);
    if(now-lastDraw>=minFrameMs) {{
      lastDraw=now;
      Plotly.relayout(divId,{{
        "scene.camera.eye.x":radius*Math.cos(angle),
        "scene.camera.eye.y":radius*Math.sin(angle),
        "scene.camera.eye.z":height,
        "scene.camera.center.x":0,
        "scene.camera.center.y":0,
        "scene.camera.center.z":0,
        "scene.camera.up.x":0,
        "scene.camera.up.y":0,
        "scene.camera.up.z":1
      }});
    }}
    requestAnimationFrame(frame);
  }}

  return {{
    play() {{
      if(running) return;
      running=true; last=performance.now(); requestAnimationFrame(frame);
    }},
    pause() {{ running=false; }}
  }};
}}

function showEvent(index) {{
  document.querySelectorAll(".event-panel").forEach((node,i) =>
    node.classList.toggle("active",i===index));
  document.querySelectorAll(".event-tab").forEach((node,i) =>
    node.classList.toggle("active",i===index));
  Object.values(rotators).forEach(r=>r.pause());
  activeEvent=index;
  const panel=document.getElementById("showcase-event-"+index+"-panel");
  panel.querySelectorAll(".plot").forEach(node=>Plotly.Plots.resize(node));
  rotators[index].play();
}}

{"".join(scripts)}
{"""Ê¶ˆñ‚á&˜FF˜'2ó–ß&˜FF˜'5≥“Á∆íÇì∞£¬˜67&óC‡£¬ˆ&ˆGì‡£¬ˆáF÷√‡¢"" ¢ˆFˆ÷ñ5˜w&óFU˜FWáBÜ˜WGWB¬vRê¢&WGW&‚˜WGW@