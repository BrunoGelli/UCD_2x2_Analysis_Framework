"""Standalone HTML export for selected 2x2 events."""
from __future__ import annotations

from html import escape
import json
import os
from pathlib import Path
import tempfile

import plotly.io as pio


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            suffix=".html.tmp",
        ) as stream:
            tmp_name = stream.name
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, path)
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)


def export_event_html(output_path, *, title, metadata, fig3d, fig2d, analysis):
    """Write one self-contained interactive event page.

    The first Plotly figure embeds plotly.js, so the result works without a
    Panel/Python server. Camera-spin frames/buttons already attached to fig3d
    are preserved.
    """
    output = Path(output_path).expanduser().resolve()
    config = {
        "responsive": True,
        "displaylogo": False,
        "scrollZoom": True,
    }

    html3d = pio.to_html(
        fig3d,
        include_plotlyjs=True,
        full_html=False,
        config=config,
    )
    html2d = pio.to_html(
        fig2d,
        include_plotlyjs=False,
        full_html=False,
        config=config,
    )
    html_analysis = pio.to_html(
        analysis,
        include_plotlyjs=False,
        full_html=False,
        config=config,
    )
    metadata_json = escape(
        json.dumps(metadata, indent=2, sort_keys=True, default=str)
    )
    safe_title = escape(str(title))

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
<style>
body {{
    margin: 0;
    background: #111318;
    color: #eceff4;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
main {{
    max-width: 1500px;
    margin: 0 auto;
    padding: 24px;
}}
h1 {{ margin-bottom: 6px; }}
.note {{ color: #b7bdc8; margin-bottom: 20px; }}
.panel {{
    background: #fff;
    border-radius: 10px;
    margin: 18px 0;
    padding: 8px;
}}
details {{
    background: #191d24;
    border-radius: 8px;
    padding: 12px 16px;
}}
pre {{
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}}
</style>
</head>
<body>
<main>
<h1>{safe_title}</h1>
<p class="note">
Interactive standalone export. Use the 3D plot's Spin/Pause controls to rotate
the event; no running Panel or Python server is required.
</p>
<details open>
<summary>Event metadata</summary>
<pre>{metadata_json}</pre>
</details>
<div class="panel">{html3d}</div>
<div class="panel">{html2d}</div>
<div class="panel">{html_analysis}</div>
</main>
</body>
</html>
"""
    _atomic_write_text(output, page)
    return output
