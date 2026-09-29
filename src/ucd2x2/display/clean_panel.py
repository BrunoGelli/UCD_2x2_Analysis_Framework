"""Session-local cleaned FLOW browser. Launched by ucd2x2 event-display --hot-mask.

The legacy app remains available without cleaning flags. No global monkeypatches,
no source writes, no import-time shared app state between browser sessions.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict

import numpy as np
import panel as pn

from ucd2x2.cli import add_cleaning_arguments, policy_from_args
from ucd2x2.core.hot_pixels import EventHitReader, HotPixelMask, EventCleaner, CleaningPolicy
from ucd2x2.core.event_scan import event_summary, load_candidates
from ucd2x2.core.geometry import module_boxes_cm
from ucd2x2.display.viz import make_plotly_3d, make_plotly_2d_projections, make_plotly_analysis

pn.extension("plotly")


def _args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--h5", required=True)
    parser.add_argument("--hot-mask")
    parser.add_argument("--candidates")
    parser.add_argument("--hit-type", choices=("prompt", "final"), default="prompt")
    parser.add_argument("--max_hits", "--max-hits", type=int, default=40000)
    parser.add_argument("--event", type=int, default=0)
    add_cleaning_arguments(parser)
    return parser.parse_known_args()[0]


def _charge_range(figure, hits):
    # Keep nonpositive hits, but don't let log10(1e-12) flatten all positive colors.
    positive = hits["Q"][np.isfinite(hits["Q"]) & (hits["Q"] > 0)]
    values = np.log10(positive) if len(positive) else np.array([0.0, 1.0])
    lo, hi = float(values.min()), float(values.max())
    if hi <= lo:
        lo, hi = lo - 0.5, hi + 0.5
    for trace in figure.data:
        if trace.type in ("scatter3d", "scattergl") and trace.marker.color is not None:
            trace.marker.cmin, trace.marker.cmax = lo, hi


class CleanBrowser:
    def __init__(self, args):
        self.args = args
        self.reader, self.mask, self.rows = None, None, []
        self.saved_policy = None
        self._loading = False
        self.file = pn.widgets.TextInput(name="Completed FLOW file", value=args.h5)
        self.mask_file = pn.widgets.TextInput(name="Trusted mask PKL (optional)", value=args.hot_mask or "")
        self.csv_file = pn.widgets.TextInput(name="Candidate CSV (optional)", value=args.candidates or "")
        self.collection = pn.widgets.Select(name="Collection to load", options=["prompt", "final"], value=args.hit_type)
        self.load_button = pn.widgets.Button(name="Load file / mask / candidates", button_type="primary")
        self.event = pn.widgets.IntSlider(name="Event index", start=0, end=1, value=0)
        self.jump = pn.widgets.IntInput(name="Jump to event index", value=0, start=0)
        self.prev = pn.widgets.Button(name="Previous event")
        self.next = pn.widgets.Button(name="Next event")
        self.clean = pn.widgets.Checkbox(name="Apply cleaning (off = raw comparison)", value=True)
        self.local = pn.widgets.IntInput(name="Max hits / pixel / event (0 = off)", value=3, start=0)
        self.mean = pn.widgets.FloatInput(name="Max hits / pixel / N_events (0 = off)", value=1.0, start=0)
        self.fraction = pn.widgets.FloatInput(name="Max fraction of events (1 = off)", value=1.0, start=0, end=1, step=0.01)
        self.disabled = pn.widgets.Checkbox(name="Remove is_disabled hits", value=True)
        self.color = pn.widgets.Select(name="Color", options=["Q", "t_drift", "ts_pps"], value="Q")
        self.point_size = pn.widgets.IntSlider(name="Point size", start=1, end=10, value=2)
        self.max_hits = pn.widgets.IntInput(name="Max plotted hits (sampling only)", value=max(1,args.max_hits), start=1)
        self.boxes = pn.widgets.Checkbox(name="Detector geometry", value=True)
        self.frame = pn.widgets.Checkbox(name="Frame nominal detector (view only)", value=True)
        self.rank_metric = pn.widgets.Select(name="Candidate sort", options={"Total cleaned Q":"total_Q", "Q in nominal detector volume":"Q_in_nominal_volume"})
        self.shown_rows = []
        self.pick = pn.widgets.Select(name="Top 100 candidates", options={})
        self.copen = pn.widgets.Button(name="Open selected candidate")
        self.cprev = pn.widgets.Button(name="Previous candidate")
        self.cnext = pn.widgets.Button(name="Next candidate")
        self.status = pn.pane.Markdown("", sizing_mode="stretch_width")
        self.rank_status = pn.pane.Markdown("")
        self.view3d = pn.pane.Plotly(height=760, sizing_mode="stretch_width")
        self.view2d = pn.pane.Plotly(height=780, sizing_mode="stretch_width")
        self.analysis = pn.pane.Plotly(height=500, sizing_mode="stretch_width")
        sidebar = pn.Column(
            pn.Card(self.file, self.mask_file, self.csv_file, self.collection, self.load_button, title="Input"),
            self.status,
            pn.Card(self.event, self.jump, pn.Row(self.prev,self.next), title="Navigation"),
            pn.Card(self.clean, self.local, self.mean, self.fraction, self.disabled, title="Cleaning"),
            pn.Card(self.rank_metric, self.pick, self.copen, pn.Row(self.cprev,self.cnext), self.rank_status, title="Candidates"),
            pn.Card(self.color,self.point_size,self.max_hits,self.boxes,self.frame,title="Display"),
            width=400, scroll=True, height=1000)
        self.layout = pn.Row(sidebar, pn.Tabs(("3D",self.view3d),("2D",self.view2d),("Distributions",self.analysis), sizing_mode="stretch_width"),
                             sizing_mode="stretch_width")
        self.load_button.on_click(self.load)
        self.rank_metric.param.watch(self.update_candidates,"value")
        self.prev.on_click(lambda _: self.goto(self.event.value-1))
        self.next.on_click(lambda _: self.goto(self.event.value+1))
        self.copen.on_click(lambda _: self.goto(self.pick.value) if self.pick.value is not None else None)
        self.cprev.on_click(lambda _: self.step_candidate(-1))
        self.cnext.on_click(lambda _: self.step_candidate(1))
        self.jump.param.watch(lambda e: self.goto(e.new), "value")
        self.pick.param.watch(lambda e: self.goto(e.new) if e.new is not None else None, "value")
        for widget in (self.event,self.clean,self.local,self.mean,self.fraction,self.disabled,
                       self.color,self.point_size,self.max_hits,self.boxes,self.frame):
            widget.param.watch(self.refresh,"value")
        pn.state.on_session_destroyed(lambda context: self.close())
        self.load()
        self.goto(args.event)

    def close(self):
        if self.reader is not None:
            self.reader.close(); self.reader = None

    def policy(self):
        return CleaningPolicy(event_max_hits=self.local.value,
                              global_mean_max=self.mean.value or None,
                              max_event_fraction=None if self.fraction.value >= 1 else self.fraction.value,
                              drop_disabled=self.disabled.value)

    def load(self, *_):
        reader = None
        try:
            reader = EventHitReader(self.file.value, self.collection.value)
            mask = HotPixelMask.load(self.mask_file.value) if self.mask_file.value.strip() else None
            if mask is not None:
                mask.validate(reader)
            policy = policy_from_args(self.args, mask)
            cleaner = EventCleaner(mask, policy)
            rows = load_candidates(self.csv_file.value, reader, cleaner, mask) if self.csv_file.value.strip() else []
            self._loading = True
            self.close()
            self.reader, self.mask, self.rows = reader, mask, rows
            self.saved_policy = asdict(policy)
            self.local.value = policy.event_max_hits
            self.mean.value = policy.global_mean_max or 0
            self.fraction.value = policy.max_event_fraction if policy.max_event_fraction is not None else 1
            self.disabled.value = policy.drop_disabled
            self.event.end = max(1,len(reader)-1)
            self.event.value = 0
            self.update_candidates()
            self._loading = False
            self.refresh()
        except Exception as exc:
            self._loading = False
            if reader is not None and reader is not self.reader:
                reader.close()
            self.status.object = f"**Load failed:** `{exc}`. No mismatched mask was applied."

    def update_candidates(self, *_):
        was_loading = self._loading
        self._loading = True
        metric = self.rank_metric.value
        self.shown_rows = sorted(self.rows, key=lambda row: -float(row.get(metric,0)))[:100]
        self.pick.options = {f"{i+1}. Event {r['event_index']} | score={float(r.get(metric,0)):.5g}":r['event_index']
                             for i,r in enumerate(self.shown_rows)}
        self._loading = was_loading

    def goto(self, event):
        if self._loading or self.reader is None or not len(self.reader):
            return
        value = max(0,min(int(event),len(self.reader)-1))
        self.event.value = value
        self.jump.value = value

    def step_candidate(self, step):
        if self.pick.disabled or not self.rows:
            return
        values = [row["event_index"] for row in self.shown_rows]
        position = values.index(self.event.value) if self.event.value in values else (-1 if step > 0 else 0)
        self.pick.value = values[(position+step) % len(values)]
        self.goto(self.pick.value)

    def refresh(self, *_):
        if self._loading or self.reader is None:
            return
        try:
            if not len(self.reader):
                self.status.object = "The file contains no events."
                return
            self.reader.check_unchanged()
            index = int(self.event.value)
            self.jump.value = index
            policy = self.policy()
            cleaner = EventCleaner(self.mask,policy)
            valid_ranking = self.clean.value and asdict(policy) == self.saved_policy
            for widget in (self.pick,self.copen,self.cprev,self.cnext):
                widget.disabled = not (valid_ranking and self.rows)
            self.rank_status.object = ("Ranking matches current cleaning." if valid_ranking and self.rows
                else "No candidates loaded, or settings changed: regenerate scan-events to use this ranking.")
            raw = self.reader.get(index)
            keep, report = cleaner.apply(raw)
            hits = raw[keep] if self.clean.value else raw
            summary = event_summary(hits)
            cap = int(self.max_hits.value)
            plotted = hits
            if len(hits) > cap:
                selected = np.sort(np.random.default_rng(index).choice(len(hits),cap,replace=False))
                plotted = hits[selected]
            kw = dict(color_mode=self.color.value,max_hits=max(1,len(plotted)),point_size=self.point_size.value)
            fig3d = make_plotly_3d(plotted,show_boxes=self.boxes.value,**kw)
            fig2d = make_plotly_2d_projections(plotted,**kw)
            if self.color.value == "Q":
                _charge_range(fig3d,hits); _charge_range(fig2d,hits)
            # Give the colorbar/legend space and preserve the camera on option changes.
            fig3d.update_layout(height=760,margin=dict(l=0,r=100,t=45,b=0),uirevision=str(index))
            if self.frame.value:
                boxes = list(module_boxes_cm().values())
                bounds = {axis:[min(getattr(b,axis+"min") for b in boxes)-1,
                               max(getattr(b,axis+"max") for b in boxes)+1] for axis in ("x","y","z")}
                fig3d.update_layout(scene=dict(xaxis_range=bounds["z"],yaxis_range=bounds["x"],zaxis_range=bounds["y"]))
            self.view3d.object, self.view2d.object = fig3d,fig2d
            self.analysis.object = make_plotly_analysis(hits)
            self.status.object = (
                f"**Loaded file:** `{self.reader.source['path']}`  \n"
                f"**Event index:** {index} | **ID:** {self.reader.event_id(index)}  \n"
                f"**Loaded collection:** {self.reader.hit_type} | **View:** {'cleaned' if self.clean.value else 'RAW'}  \n"
                f"Raw: **{len(raw):,}** → clean: **{report['clean_hits']:,}**  \n"
                f"Removed: global {report['removed_global']:,}, local {report['removed_local']:,}, "
                f"disabled {report['removed_disabled']:,}, invalid {report['removed_invalid']:,}  \n"
                f"**View ΣQ:** {summary['total_Q']:.6g} (signed input units)  \n"
                f"**Nominal volume:** {summary['n_in_nominal_volume']:,}/{len(hits):,} hits; Q={summary['Q_in_nominal_volume']:.6g}  \n"
                f"**Pixels:** {summary['n_unique_pixels']:,} | **Plotted:** {len(plotted):,}/{len(hits):,}  \n"
                "Nominal volume is a stored-coordinate diagnostic (±1 cm), not a timing correction or physics cut. "
                "Q color range uses positive charges; Q≤0 stays visible at the low end. "
                "Distributions use every hit in the selected view, not the plotting subsample.")
        except Exception as exc:
            self.status.object = f"**Display failed:** `{exc}`"


browser = CleanBrowser(_args())
browser.layout.servable(title="2×2 cleaned event browser")
