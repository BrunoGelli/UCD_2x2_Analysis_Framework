"""Panel event display UI.

Run:
  panel serve -m ucd2x2.display.app_panel --show --args --h5 /path/to/file.FLOW.hdf5
"""

from __future__ import annotations

import argparse
import bisect
import os
from pathlib import Path

import numpy as np
import panel as pn
import plotly.graph_objects as go

from ucd2x2.core.clustering import angle_to_z_of_centroid_line
from ucd2x2.stage2.config import dump_pipeline_config, load_pipeline_config, default_registry, pipeline_from_dict
from ucd2x2.stage2.pipeline_ui import (
    UIStepState,
    add_step,
    config_to_ui_steps,
    move_step,
    remove_step,
    ui_steps_to_config,
    widgets_for_step,
)
from ucd2x2.core.io import FlowFile
from ucd2x2.core.truth import summarize_truth_event_tree
import ucd2x2.display.viz as viz
from ucd2x2.display.viz import (
    make_plotly_2d_projections,
    make_plotly_3d,
    make_plotly_analysis,
    truth_trajectory_overlay_diagnostic,
)

pn.extension("plotly")


def _parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--h5", type=str, default=os.environ.get("TWOBYTWO_H5", ""))
    parser.add_argument("--max_hits", type=int, default=40000)
    return parser.parse_known_args()[0]


class AppState:
    def __init__(self, path: str, max_hits: int):
        self.path = path
        self.max_hits = max_hits
        self.flow = None
        self.muon_indices = []

    def open(self, path: str):
        self.close()
        self.path = path
        if not path:
            return
        self.flow = FlowFile.open(path)
        self.muon_indices = self.flow.muon_event_indices()

    def close(self):
        if self.flow is not None:
            self.flow.close()
            self.flow = None
        self.muon_indices = []


ARGS = _parse_args()
state = AppState(ARGS.h5, ARGS.max_hits)
if state.path:
    state.open(state.path)

# ---------- widgets ----------
file_input = pn.widgets.TextInput(name="HDF5 path", value=state.path)
open_btn = pn.widgets.Button(name="Open", button_type="primary")
status = pn.pane.Markdown("", height=160)

# navigation
event_slider = pn.widgets.IntSlider(name="Event", start=0, end=0, value=0)
event_input = pn.widgets.IntInput(name="Jump to event", value=0, step=1)
prev_btn = pn.widgets.Button(name="◀ Prev", width=90)
next_btn = pn.widgets.Button(name="Next ▶", button_type="primary", width=90)
muon_only = pn.widgets.Toggle(name="Muon-only scan", value=False)

# display
hit_type = pn.widgets.Select(name="Hit type", options=["prompt", "final"], value="prompt")
color_mode = pn.widgets.Select(name="Color mode", options=["Q", "t_drift", "ts_pps", "muon_region"], value="Q")
max_hits = pn.widgets.IntInput(name="Max hits", value=ARGS.max_hits, step=1000, start=1000)
point_size = pn.widgets.IntSlider(name="Point size", start=1, end=10, value=2)
show_boxes = pn.widgets.Checkbox(name="Show geometry boxes", value=True)

# truth
show_truth = pn.widgets.Checkbox(name="Enable truth overlay", value=False)
show_truth_segments = pn.widgets.Checkbox(name="Show truth segments", value=True)
show_truth_traj_parents = pn.widgets.Checkbox(name="Show truth trajectory parents", value=False)
truth_tree_max_entries = pn.widgets.IntInput(name="Truth tree max entries", value=10, start=1, step=1)
truth_mode = pn.widgets.Select(name="Truth mode", options=["backtrack", "window"], value="backtrack")
truth_event = pn.widgets.Select(name="Window truth event_id", options=["auto"], value="auto")
show_vertices = pn.widgets.Checkbox(name="Show truth vertices", value=True)
show_all_window_vertices = pn.widgets.Checkbox(name="Window mode: all vertices in window", value=False)
mc_only_muons = pn.widgets.Checkbox(name="Truth only muons (|pdg|=13)", value=False)
mc_max_segments = pn.widgets.IntInput(name="Draw max truth segments", value=3000, step=500, start=0)
mc_topk = pn.widgets.IntInput(name="Backtrack top-K segments", value=2000, step=200, start=0)
mc_minw = pn.widgets.FloatInput(name="Backtrack min weight", value=0.0, step=0.01)

# muon
show_muon = pn.widgets.Checkbox(name="Show rock muon track", value=False)

# stage2 pipeline editor
stage2_cfg_path = pn.widgets.TextInput(name="Stage2 config path", value="configs/stage2/repeated_pixel_then_dbscan.yaml")
stage2_load_btn = pn.widgets.Button(name="Load Stage 2 config")
stage2_save_btn = pn.widgets.Button(name="Save Stage 2 config")
stage2_step_select = pn.widgets.Select(name="Add step", options=default_registry().names(), value=default_registry().names()[0])
stage2_add_step_btn = pn.widgets.Button(name="Add step")
stage2_cfg_status = pn.pane.Markdown("", height=80)
stage2_steps_column = pn.Column()
clusters_info = pn.pane.Markdown("", height=180)

_stage2_steps_state = config_to_ui_steps(load_pipeline_config(stage2_cfg_path.value), registry=default_registry())
_stage2_step_widgets = []

view3d = pn.pane.Plotly(sizing_mode="stretch_both")
view2d = pn.pane.Plotly(sizing_mode="stretch_both")
analysis_text = pn.pane.Markdown("", sizing_mode="stretch_width")
analysis_plot = pn.pane.Plotly(min_height=450, sizing_mode="stretch_width")
view_analysis = pn.Column(analysis_text, analysis_plot, sizing_mode="stretch_both")
truth_tree_markdown = pn.pane.Markdown("", sizing_mode="stretch_both")

# stage2 config
stage2_cfg_path = pn.widgets.TextInput(name="Stage2 config path", value="configs/stage2/dbscan_default.yaml")
stage2_load_btn = pn.widgets.Button(name="Load Stage 2 config")
stage2_save_btn = pn.widgets.Button(name="Save Stage 2 config")
stage2_cfg_status = pn.pane.Markdown("", height=80)



def _dbscan_widget_values():
    return {
        "show_clusters": bool(show_clusters.value),
        "eps_cm": float(db_eps.value),
        "min_samples": int(db_min.value),
        "cluster_min_hits": int(cluster_min_hits.value),
        "cluster_max_extent_cm": float(cluster_max_extent.value),
    }


def _apply_dbscan_widget_values(values):
    show_clusters.value = bool(values.get("show_clusters", show_clusters.value))
    db_eps.value = float(values.get("eps_cm", db_eps.value))
    db_min.value = int(values.get("min_samples", db_min.value))
    cluster_min_hits.value = int(values.get("cluster_min_hits", cluster_min_hits.value))
    cluster_max_extent.value = float(values.get("cluster_max_extent_cm", cluster_max_extent.value))


def _set_stage2_cfg_status(message: str, ok: bool = True):
    icon = "✅" if ok else "❌"
    stage2_cfg_status.object = f"{icon} {message}"


def _save_stage2_config(_=None):
    try:
        config = build_stage2_config_from_dbscan_values(_dbscan_widget_values())
        yaml_text = dump_pipeline_config(config)
        path = Path(stage2_cfg_path.value.strip())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml_text)
        _set_stage2_cfg_status(f"Saved Stage 2 config to `{path}`", ok=True)
    except Exception as exc:
        _set_stage2_cfg_status(f"Failed to save config: {exc}", ok=False)


def _load_stage2_config(_=None):
    try:
        path = Path(stage2_cfg_path.value.strip())
        config = load_pipeline_config(path)
        values = _dbscan_widget_values()
        apply_stage2_config_to_dbscan_values(config, values)
        _apply_dbscan_widget_values(values)
        _set_stage2_cfg_status(f"Loaded Stage 2 config from `{path}`", ok=True)
    except Exception as exc:
        _set_stage2_cfg_status(f"Failed to load config: {exc}", ok=False)

def _stage2_config_from_ui():
    steps = []
    for row in _stage2_step_widgets:
        params = {k: w.value for k, w in row["params_widgets"].items()}
        steps.append(UIStepState(name=row["name"], enabled=bool(row["enabled"].value), params=params))
    return ui_steps_to_config(steps)


def _rebuild_stage2_step_cards():
    global _stage2_step_widgets
    _stage2_step_widgets = []
    stage2_steps_column.objects = []
    for idx, step in enumerate(_stage2_steps_state):
        params_widgets = widgets_for_step(step.name, values=step.params, registry=default_registry())
        enabled = pn.widgets.Checkbox(name="Enabled", value=bool(step.enabled))
        up_btn = pn.widgets.Button(name="↑", width=35)
        dn_btn = pn.widgets.Button(name="↓", width=35)
        rm_btn = pn.widgets.Button(name="Remove", button_type="danger", width=80)

        def _make_move(i, d):
            def _cb(_=None):
                global _stage2_steps_state
                _stage2_steps_state = move_step(_stage2_steps_state, i, d)
                _rebuild_stage2_step_cards()
                _refresh_views()
            return _cb

        def _make_remove(i):
            def _cb(_=None):
                global _stage2_steps_state
                _stage2_steps_state = remove_step(_stage2_steps_state, i)
                _rebuild_stage2_step_cards()
                _refresh_views()
            return _cb

        up_btn.on_click(_make_move(idx, -1)); dn_btn.on_click(_make_move(idx, 1)); rm_btn.on_click(_make_remove(idx))
        for w in params_widgets.values():
            w.param.watch(_refresh_views, "value")
        enabled.param.watch(_refresh_views, "value")

        card = pn.Card(enabled, *params_widgets.values(), pn.Row(up_btn, dn_btn, rm_btn), title=step.name, collapsed=True)
        stage2_steps_column.append(card)
        _stage2_step_widgets.append({"name": step.name, "enabled": enabled, "params_widgets": params_widgets})


def _add_stage2_step(_=None):
    global _stage2_steps_state
    _stage2_steps_state = add_step(_stage2_steps_state, str(stage2_step_select.value), registry=default_registry())
    _rebuild_stage2_step_cards()
    _refresh_views()


def _save_stage2_config(_=None):
    try:
        config = _stage2_config_from_ui()
        yaml_text = dump_pipeline_config(config)
        path = Path(stage2_cfg_path.value.strip())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml_text)
        _set_stage2_cfg_status(f"Saved Stage 2 config to `{path}`", ok=True)
    except Exception as exc:
        _set_stage2_cfg_status(f"Failed to save config: {exc}", ok=False)


def _load_stage2_config(_=None):
    global _stage2_steps_state
    try:
        path = Path(stage2_cfg_path.value.strip())
        cfg = load_pipeline_config(path)
        _stage2_steps_state = config_to_ui_steps(cfg, registry=default_registry())
        _rebuild_stage2_step_cards()
        _refresh_views()
        _set_stage2_cfg_status(f"Loaded Stage 2 config from `{path}`", ok=True)
    except Exception as exc:
        _set_stage2_cfg_status(f"Failed to load config: {exc}", ok=False)

def _set_stage2_cfg_status(message: str, ok: bool = True):
    icon = "✅" if ok else "❌"
    stage2_cfg_status.object = f"{icon} {message}"


def _set_status(message: str, ok: bool = True):
    icon = "✅" if ok else "❌"
    status.object = f"### Status {icon}\n{message}"


def _sync_slider_bounds():
    if state.flow is None:
        event_slider.start = event_slider.end = event_slider.value = 0
        event_input.value = 0
        return
    end = max(0, state.flow.n_events() - 1)
    event_slider.start, event_slider.end = 0, end
    event_slider.value = min(event_slider.value, end)
    event_input.value = int(event_slider.value)


def _goto_event(ev: int):
    event_slider.value = max(event_slider.start, min(event_slider.end, int(ev)))


def _next_event(_=None):
    if state.flow is None:
        return
    if muon_only.value and state.muon_indices:
        pos = bisect.bisect_right(state.muon_indices, int(event_slider.value))
        _goto_event(state.muon_indices[pos % len(state.muon_indices)])
    else:
        _goto_event(int(event_slider.value) + 1)


def _prev_event(_=None):
    if state.flow is None:
        return
    if muon_only.value and state.muon_indices:
        pos = bisect.bisect_left(state.muon_indices, int(event_slider.value)) - 1
        _goto_event(state.muon_indices[pos % len(state.muon_indices)])
    else:
        _goto_event(int(event_slider.value) - 1)


def _selected_truth_event_id():
    if truth_event.value == "auto":
        return None
    try:
        return int(truth_event.value)
    except Exception:
        return None


def _refresh_control_visibility():
    truth_enabled = bool(show_truth.value)
    truth_mode.visible = truth_enabled
    show_truth_segments.visible = truth_enabled
    show_truth_traj_parents.visible = truth_enabled
    truth_tree_max_entries.visible = truth_enabled
    truth_event.visible = truth_enabled and truth_mode.value == "window"
    show_all_window_vertices.visible = truth_enabled and truth_mode.value == "window"
    show_vertices.visible = truth_enabled
    mc_only_muons.visible = truth_enabled
    mc_max_segments.visible = truth_enabled
    mc_topk.visible = truth_enabled and truth_mode.value == "backtrack"
    mc_minw.visible = truth_enabled and truth_mode.value == "backtrack"

    clusters_info.visible = True


def _compute_clusters(hits, muon_track, event_index):
    config = _stage2_config_from_ui()
    pipeline = pipeline_from_dict(config, registry=default_registry())
    context = {"hits": hits, "muon_track": muon_track, "event_index": int(event_index)}
    out = pipeline.run(context)
    clusters = out.get("clusters", [])
    if not clusters:
        clusters_info.object = "**Clusters kept:** 0"
        return []
    lines = [f"- cluster {i}: nhits={c.n_hits}, sumQ={c.total_Q:.2g}, max={c.extent_max_cm:.2f} cm" for i, c in enumerate(clusters)]
    theta_line = angle_to_z_of_centroid_line(clusters)
    suffix = "\n\n**Centroid-line fit:** need ≥2 clusters"
    if theta_line is not None:
        suffix = f"\n\n**Centroid-line angle to z:** {theta_line * 180 / np.pi:.1f}°"
    clusters_info.object = "**Clusters kept:**\n" + "\n".join(lines) + suffix
    return clusters


def _analysis_markdown(hits, clusters, truth_info):
    lines = [
        f"### Event analysis",
        f"- hits: **{len(hits)}**",
        f"- total Q: **{np.nansum(hits['Q'].astype(float)):.4g}**" if len(hits) else "- total Q: **0**",
    ]
    if clusters is None:
        lines.append("- clusters: *(disabled)*")
    else:
        lines.append(f"- clusters kept: **{len(clusters)}**")
        if len(clusters):
            for i, c in enumerate(clusters[:8]):
                lines.append(f"  - cluster {i}: nhits={c.n_hits}, sumQ={c.total_Q:.3g}, max_extent={c.extent_max_cm:.2f} cm")
    if truth_info is None:
        lines.append("- truth: *(disabled)*")
    else:
        lines.append(f"- truth mode: **{truth_info.get('selection','?')}**")
        lines.append(f"- truth segments: **{truth_info.get('chosen_n_segments', 0)}**")
        if truth_info.get("multi", False):
            lines.append("- window has multiple truth event_ids")
    return "\n".join(lines)


def _refresh_views(*_):
    _refresh_control_visibility()
    if state.flow is None:
        view3d.object = None
        view2d.object = None
        analysis_text.object = ""
        analysis_plot.object = None
        return

    ev = int(event_slider.value)
    event_input.value = ev
    hits = state.flow.get_event_hits(ev, hit_type=hit_type.value)
    muon_track = state.flow.get_muon_track_for_event(ev) if show_muon.value else None

    clusters = _compute_clusters(hits, muon_track, ev)

    truth_segments, truth_vertices, truth_info, truth_trajectories = None, None, None, None
    if show_truth.value:
        if show_truth_segments.value:
            truth_segments, truth_info = state.flow.get_truth_overlay(
            ev,
            mode=truth_mode.value,
            hit_type=hit_type.value,
            top_k_segments=int(mc_topk.value),
            min_weight=float(mc_minw.value),
            truth_event_id=_selected_truth_event_id(),
            mc_only_muons=bool(mc_only_muons.value),
        )
        else:
            truth_info = {"selection": truth_mode.value, "missing": False, "chosen_n_segments": 0}
            truth_segments = None
        truth_trajectories = state.flow.get_truth_trajectories_for_event(ev, truth_event_id=_selected_truth_event_id())

        if show_vertices.value:
            truth_vertices = state.flow.get_truth_vertices(
                ev,
                mode=truth_mode.value,
                hit_type=hit_type.value,
                top_k_segments=int(mc_topk.value),
                min_weight=float(mc_minw.value),
                truth_event_id=_selected_truth_event_id(),
                include_all_window_vertices=bool(show_all_window_vertices.value),
            )

        if truth_mode.value == "window":
            ids = truth_info.get("truth_event_ids", []) if truth_info else []
            truth_event.options = ["auto"] + [str(v) for v in ids]
            if truth_event.value not in truth_event.options:
                truth_event.value = "auto"
        else:
            truth_event.options = ["auto"]
            truth_event.value = "auto"

    truth_summary = "truth overlay off"
    if truth_info is not None:
        if truth_info.get("missing", True):
            truth_summary = f"{truth_mode.value}: missing"
        else:
            truth_summary = f"{truth_mode.value}: segs={truth_info.get('chosen_n_segments', 0)}"
            if truth_info.get("multi", False):
                truth_summary += " (multi-window)"

    fig3d = viz.make_plotly_3d(
        hits,
        color_mode=color_mode.value,
        max_hits=int(max_hits.value),
        point_size=int(point_size.value),
        show_boxes=bool(show_boxes.value),
        muon_track=muon_track,
        clusters=clusters,
        mc_segments=truth_segments,
        mc_vertices=truth_vertices,
        mc_max_segments=int(mc_max_segments.value),
        mc_only_muons=bool(mc_only_muons.value),
        mc_label=f"MC segments ({truth_mode.value})",
        mc_trajectories=truth_trajectories,
        show_truth_trajectories=bool(show_truth_traj_parents.value),
    )
    fig2d = make_plotly_2d_projections(
        hits,
        color_mode=color_mode.value,
        max_hits=int(max_hits.value),
        point_size=max(2, int(point_size.value)),
        muon_track=muon_track,
    )
    fig_analysis = make_plotly_analysis(hits, clusters=clusters)

    view3d.object = fig3d
    view2d.object = fig2d
    analysis_text.object = _analysis_markdown(hits, clusters, truth_info)
    analysis_plot.object = fig_analysis

    tables_available = state.flow.get_truth_tables_available() if state.flow is not None else {}
    truth_tree_markdown.object = summarize_truth_event_tree(
        truth_segments,
        truth_trajectories,
        max_entries=int(truth_tree_max_entries.value),
        tables_available=tables_available,
    )
    vertex_rows = truth_vertices
    if vertex_rows is None:
        vertex_rows = state.flow.get_truth_mc_hdr_for_event(ev, truth_event_id=_selected_truth_event_id())
    seg_names = ", ".join((truth_segments.dtype.names or ())) if truth_segments is not None and len(truth_segments) else "n/a"
    traj_names = ", ".join((truth_trajectories.dtype.names or ())) if truth_trajectories is not None and len(truth_trajectories) else "n/a"
    vtx_names = ", ".join((vertex_rows.dtype.names or ())) if vertex_rows is not None and len(vertex_rows) else "n/a"
    tr_ok, tr_reason = truth_trajectory_overlay_diagnostic(truth_trajectories)
    diag = (
        "\n\n---\n"
        "**Diagnostics**  \n"
        f"tables: {tables_available}  \n"
        f"segment fields: {seg_names}  \n"
        f"trajectory fields: {traj_names}  \n"
        f"vertex/header fields: {vtx_names}  \n"
        f"trajectory overlay drawable: {tr_ok} ({tr_reason})"
    )
    truth_tree_markdown.object += diag
    _set_status(
        f"**File:** `{os.path.basename(state.path)}`  \n"
        f"**Event:** `{ev}`  \n"
        f"**Hit type:** `{hit_type.value}`  \n"
        f"**N hits:** `{len(hits)}`  \n"
        f"**Truth:** {truth_summary}",
        ok=True,
    )


def _open_file(_=None):
    path = file_input.value.strip()
    if not path:
        state.close()
        _sync_slider_bounds()
        _set_status("No file path provided.", ok=False)
        return
    if not os.path.exists(path):
        _set_status(f"File not found: `{path}`", ok=False)
        return
    try:
        state.open(path)
        _sync_slider_bounds()
        _refresh_views()
    except Exception as exc:
        _set_status(f"Failed to open file: `{exc}`", ok=False)


# ---------- callbacks ----------
open_btn.on_click(_open_file)
next_btn.on_click(_next_event)
prev_btn.on_click(_prev_event)
stage2_load_btn.on_click(_load_stage2_config)
stage2_save_btn.on_click(_save_stage2_config)
stage2_add_step_btn.on_click(_add_stage2_step)

event_slider.param.watch(lambda e: _goto_event(e.new), "value")
event_input.param.watch(lambda e: _goto_event(e.new), "value")

for w in [
    event_slider,
    hit_type,
    color_mode,
    max_hits,
    point_size,
    show_boxes,
    show_muon,
    show_truth,
    show_truth_segments,
    show_truth_traj_parents,
    truth_tree_max_entries,
    truth_mode,
    truth_event,
    show_vertices,
    show_all_window_vertices,
    mc_only_muons,
    mc_max_segments,
    mc_topk,
    mc_minw,
]:
    w.param.watch(_refresh_views, "value")

_sync_slider_bounds()
_rebuild_stage2_step_cards()
_refresh_control_visibility()
if state.flow is not None:
    _refresh_views()
else:
    _set_status("Provide an HDF5 path and click **Open**.")

navigation_card = pn.Card(pn.Row(prev_btn, next_btn), muon_only, event_slider, event_input, title="Navigation", collapsed=False)
display_card = pn.Card(hit_type, color_mode, max_hits, point_size, show_boxes, title="Display options", collapsed=False)
truth_card = pn.Card(
    show_truth,
    show_truth_segments,
    show_truth_traj_parents,
    truth_tree_max_entries,
    truth_mode,
    truth_event,
    show_vertices,
    show_all_window_vertices,
    mc_only_muons,
    mc_max_segments,
    mc_topk,
    mc_minw,
    title="Truth overlay",
    collapsed=False,
)
stage2_cfg_card = pn.Card(stage2_cfg_path, pn.Row(stage2_load_btn, stage2_save_btn), pn.Row(stage2_step_select, stage2_add_step_btn), stage2_steps_column, clusters_info, stage2_cfg_status, title="Stage 2 pipeline", collapsed=False)
muon_card = pn.Card(show_muon, title="Muon track", collapsed=True)

sidebar = pn.Column(
    pn.Row(file_input, open_btn),
    status,
    navigation_card,
    display_card,
    truth_card,
    stage2_cfg_card,
    muon_card,
    width=420,
    sizing_mode="stretch_height",
)

main_tabs = pn.Tabs(("3D", view3d), ("2D", view2d), ("Analysis", view_analysis), ("Truth Tree", truth_tree_markdown), dynamic=True)
layout = pn.Row(sidebar, main_tabs, sizing_mode="stretch_both")
layout.servable(title="2x2 Event Display")
