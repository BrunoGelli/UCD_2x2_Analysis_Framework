from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ucd2x2.core.geometry import module_boxes_cm
from ucd2x2.core.selection import muon_region_labels


def _safe_log10(x, eps=1e-12):
    return np.log10(np.clip(np.asarray(x), eps, None))


def color_array(hits, mode: str, muon_track=None, r_core=5.0, r_near=25.0):
    if mode == "Q":
        q = hits["Q"].astype(float)
        positive = np.isfinite(q) & (q > 0)
        # Nonpositive charge stays in the data/plot, at the lowest positive color.
        # Mapping it to log10(1e-12) instead destroys useful positive-Q contrast.
        floor = float(q[positive].min()) if np.any(positive) else 1.0
        return np.log10(np.where(positive, q, floor)), "log10(Q)"
    if mode == "t_drift":
        return hits["t_drift"].astype(float), "t_drift"
    if mode == "ts_pps":
        c = hits["ts_pps"].astype(float)
        return c - np.nanmin(c), "ts_pps - min"
    if mode == "muon_region":
        return muon_region_labels(hits, muon_track, r_core=r_core, r_near=r_near), "muon region"
    raise ValueError("mode must be one of: Q, t_drift, ts_pps, muon_region")



def detector_view_bounds(padding_cm=2.0):
    """Return stable detector-coordinate bounds for display framing only."""
    boxes = list(module_boxes_cm().values())
    pad = float(padding_cm)
    return {
        axis: [
            min(getattr(box, axis + "min") for box in boxes) - pad,
            max(getattr(box, axis + "max") for box in boxes) + pad,
        ]
        for axis in ("x", "y", "z")
    }


def apply_detector_frame(fig3d, fig2d=None, padding_cm=2.0):
    """Lock plots to the nominal 2x2 detector envelope.

    Plotly 3D uses (z, x, y) as its displayed axes in this framework. Hits
    outside these ranges are still present in the event and diagnostics; they
    simply no longer force the visual scale to expand by metres.
    """
    bounds = detector_view_bounds(padding_cm)
    fig3d.update_layout(
        scene=dict(
            xaxis=dict(range=bounds["z"], autorange=False),
            yaxis=dict(range=bounds["x"], autorange=False),
            zaxis=dict(range=bounds["y"], autorange=False),
            aspectmode="cube",
        )
    )
    if fig2d is not None:
        # XY
        fig2d.update_xaxes(range=bounds["x"], autorange=False, row=1, col=1)
        fig2d.update_yaxes(range=bounds["y"], autorange=False, row=1, col=1)
        # XZ
        fig2d.update_xaxes(range=bounds["x"], autorange=False, row=1, col=2)
        fig2d.update_yaxes(range=bounds["z"], autorange=False, row=1, col=2)
        # YZ
        fig2d.update_xaxes(range=bounds["y"], autorange=False, row=2, col=1)
        fig2d.update_yaxes(range=bounds["z"], autorange=False, row=2, col=1)
    return bounds


def camera_for_angle(angle, radius=1.75, height=0.85):
    """Return a Plotly 3D camera on a horizontal orbit around the detector."""
    return dict(
        eye=dict(
            x=float(radius * np.cos(angle)),
            y=float(radius * np.sin(angle)),
            z=float(height),
        ),
        center=dict(x=0.0, y=0.0, z=0.0),
        up=dict(x=0.0, y=0.0, z=1.0),
    )


def add_camera_spin(fig, seconds_per_rotation=16.0, n_frames=120,
                    radius=1.75, height=0.85):
    """Add Play/Pause camera frames for standalone Plotly/HTML output."""
    n_frames = max(12, int(n_frames))
    seconds_per_rotation = max(1.0, float(seconds_per_rotation))
    duration_ms = max(20, int(1000.0 * seconds_per_rotation / n_frames))

    frames = []
    for i in range(n_frames):
        angle = 2.0 * np.pi * i / n_frames
        camera = camera_for_angle(angle, radius=radius, height=height)
        frames.append(
            go.Frame(
                name=f"camera-spin-{i:03d}",
                layout=go.Layout(scene_camera=camera),
            )
        )
    fig.frames = frames

    menus = list(fig.layout.updatemenus) if fig.layout.updatemenus else []
    menus.append(dict(
        type="buttons",
        direction="left",
        x=0.0,
        y=1.08,
        xanchor="left",
        yanchor="top",
        showactive=False,
        name="camera-spin-controls",
        buttons=[
            dict(
                label="▶ Spin",
                method="animate",
                args=[
                    None,
                    dict(
                        frame=dict(duration=duration_ms, redraw=False),
                        transition=dict(duration=duration_ms, easing="linear"),
                        fromcurrent=True,
                        mode="immediate",
                    ),
                ],
            ),
            dict(
                label="⏸ Pause",
                method="animate",
                args=[
                    [None],
                    dict(
                        frame=dict(duration=0, redraw=False),
                        transition=dict(duration=0),
                        mode="immediate",
                    ),
                ],
            ),
        ],
    ))
    fig.update_layout(updatemenus=menus)
    return fig

def _sample_hits(hits, max_hits: int):
    if max_hits < 1:
        raise ValueError("max_hits must be positive")
    if len(hits) > max_hits:
        return hits[np.random.choice(len(hits), size=max_hits, replace=False)]
    return hits


def _hover_customdata(hits):
    names = hits.dtype.names or ()
    def field(name, default):
        return hits[name].astype(float) if name in names else np.full(len(hits), default)
    return np.stack([field("Q", np.nan), field("t_drift", np.nan), field("ts_pps", np.nan),
                     field("io_group", -1), field("io_channel", -1)], axis=1)


def _box_edge_coordinates(box, depth_cm=0.0):
    """All 12 edges; Plotly coordinates are detector z,x,y (as before)."""
    zmin, zmax = box.zmin-depth_cm/2, box.zmax+depth_cm/2
    corners = np.array([[box.xmin,box.ymin,zmin],[box.xmax,box.ymin,zmin],
        [box.xmax,box.ymax,zmin],[box.xmin,box.ymax,zmin],
        [box.xmin,box.ymin,zmax],[box.xmax,box.ymin,zmax],
        [box.xmax,box.ymax,zmax],[box.xmin,box.ymax,zmax]],dtype=float)
    edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
    x,y,z = [],[],[]
    for i,j in edges:
        x += [corners[i,2],corners[j,2],None]
        y += [corners[i,0],corners[j,0],None]
        z += [corners[i,1],corners[j,1],None]
    return x,y,z


def make_plotly_2d_projections(hits, color_mode="Q", max_hits=40000, point_size=3, muon_track=None):
    if len(hits) == 0:
        fig = go.Figure(); fig.update_layout(title="No hits in event"); return fig
    hits = _sample_hits(hits,max_hits)
    c,clabel = color_array(hits,color_mode,muon_track=muon_track)
    customdata = _hover_customdata(hits)
    hover = ("x=%{x:.2f}<br>y=%{y:.2f}<br>Q=%{customdata[0]:.3g}"
             "<br>t_drift=%{customdata[1]:.3g}<br>ts_pps=%{customdata[2]:.3g}"
             "<br>IO group=%{customdata[3]}<br>IO channel=%{customdata[4]}<extra></extra>")
    fig = make_subplots(rows=2,cols=2,subplot_titles=("XY","XZ","YZ","Charge histogram"))
    projections = [(hits["x"],hits["y"],1,1,"x [cm]","y [cm]"),
                   (hits["x"],hits["z"],1,2,"x [cm]","z [cm]"),
                   (hits["y"],hits["z"],2,1,"y [cm]","z [cm]")]
    for i,(xx,yy,r,col,xl,yl) in enumerate(projections):
        fig.add_trace(go.Scattergl(x=xx,y=yy,mode="markers",
            marker=dict(size=point_size,color=c,colorscale="Viridis",showscale=(i==0),colorbar=dict(title=clabel)),
            customdata=customdata,hovertemplate=hover,showlegend=False),row=r,col=col)
        fig.update_xaxes(title_text=xl,row=r,col=col); fig.update_yaxes(title_text=yl,row=r,col=col)
    q = hits["Q"].astype(float); q = q[np.isfinite(q)]
    fig.add_trace(go.Histogram(x=q,nbinsx=80,marker=dict(color="#4c78a8"),showlegend=False,
                  hovertemplate="Q=%{x:.3g}<br>count=%{y}<extra></extra>"),row=2,col=2)
    fig.update_xaxes(title_text="Q",row=2,col=2); fig.update_yaxes(title_text="count",row=2,col=2)
    fig.update_layout(height=780,margin=dict(l=10,r=10,t=40,b=10),title="2D projections")
    return fig


def make_plotly_3d(hits,color_mode="Q",max_hits=40000,point_size=2,show_boxes=True,
                   muon_track=None,r_core=5.0,r_near=25.0,clusters=None,
                   mc_segments=None,mc_vertices=None,mc_max_segments=3000,
                   mc_only_muons=False,mc_label="MC truth segments",mc_trajectories=None,
                   show_truth_trajectories=False):
    if len(hits) == 0:
        fig = go.Figure(); fig.update_layout(title="No hits in event"); return fig
    hits = _sample_hits(hits,max_hits)
    c,clabel = color_array(hits,color_mode,muon_track=muon_track,r_core=r_core,r_near=r_near)
    fig = go.Figure()
    if color_mode == "muon_region":
        labels = c.astype(int)
        for lab,name,col in [(0,f"core (≤ {r_core:g} cm)","red"),(1,f"near (≤ {r_near:g} cm)","orange"),(2,"far","gray")]:
            m = labels==lab
            fig.add_trace(go.Scatter3d(x=hits["z"][m],y=hits["x"][m],z=hits["y"][m],mode="markers",
                          marker=dict(size=point_size,color=col),name=name))
    else:
        fig.add_trace(go.Scatter3d(x=hits["z"],y=hits["x"],z=hits["y"],mode="markers",name="hits",
            customdata=np.stack([hits["Q"].astype(float)],axis=1),
            hovertemplate="z=%{x:.2f}<br>x=%{y:.2f}<br>y=%{z:.2f}<br>Q=%{customdata[0]:.4g}<extra></extra>",
            marker=dict(size=point_size,color=c,colorscale="Viridis",showscale=True,
                        colorbar=dict(title=clabel,len=0.55,thickness=16,y=0.48))))
    if show_boxes:
        for _,box in module_boxes_cm().items():
            x,y,z = _box_edge_coordinates(box)
            fig.add_trace(go.Scatter3d(x=x,y=y,z=z,mode="lines",line=dict(width=2),showlegend=False,opacity=0.5))
    if muon_track is not None:
        a = np.array([muon_track["x_start"],muon_track["y_start"],muon_track["z_start"]],dtype=float)
        b = np.array([muon_track["x_end"],muon_track["y_end"],muon_track["z_end"]],dtype=float)
        fig.add_trace(go.Scatter3d(x=[a[2],b[2]],y=[a[0],b[0]],z=[a[1],b[1]],mode="lines",
                                  line=dict(width=6),name="rock muon track"))
    if clusters:
        for i,cluster in enumerate(clusters):
            cen = np.asarray(cluster.centroid,dtype=float)
            fig.add_trace(go.Scatter3d(x=[cen[2]],y=[cen[0]],z=[cen[1]],mode="markers",
                          marker=dict(size=7),name=f"cluster {i}" if i==0 else "cluster",showlegend=(i==0)))
    if mc_segments is not None and len(mc_segments):
        segments = mc_segments
        if mc_only_muons and "pdg_id" in (segments.dtype.names or ()):
            segments = segments[np.abs(segments["pdg_id"])==13]
        if mc_max_segments and len(segments)>mc_max_segments:
            segments = segments[np.random.choice(len(segments),size=mc_max_segments,replace=False)]
        x,y,z,hover = [],[],[],[]
        for segment in segments:
            x += [float(segment["z_start"]),float(segment["z_end"]),None]
            y += [float(segment["x_start"]),float(segment["x_end"]),None]
            z += [float(segment["y_start"]),float(segment["y_end"]),None]
            names = segments.dtype.names or ()
            pdg = int(segment["pdg_id"]) if "pdg_id" in names else -999
            de = float(segment["dE"]) if "dE" in names else float("nan")
            hover += [f"pdg={pdg}<br>dE={de:.3g}",f"pdg={pdg}<br>dE={de:.3g}",None]
        fig.add_trace(go.Scatter3d(x=x,y=y,z=z,mode="lines",line=dict(width=4),name=mc_label,
                                  opacity=0.7,hoverinfo="text",text=hover))
    if show_truth_trajectories:
        trace = _trajectory_trace(mc_trajectories)
        if trace is not None:
            fig.add_trace(trace)
    if mc_vertices is not None and len(mc_vertices)>0 and "vertex" in (mc_vertices.dtype.names or ()):
        vx,vy,vz = (mc_vertices["vertex"][:,i].astype(float) for i in (0,1,2))
        hover = []
        for row in mc_vertices:
            names = mc_vertices.dtype.names or ()
            eid = int(row["event_id"]) if "event_id" in names else -1
            iid = int(row["interaction_id"]) if "interaction_id" in names else -1
            vid = int(row["vertex_id"]) if "vertex_id" in names else -1
            hover.append(f"event_id={eid}<br>interaction_id={iid}<br>vertex_id={vid}")
        fig.add_trace(go.Scatter3d(x=vz,y=vx,z=vy,mode="markers",marker=dict(size=6,symbol="diamond"),
                                  name="MC vertices",text=hover,hoverinfo="text"))
    fig.update_layout(scene=dict(xaxis_title="z [cm]",yaxis_title="x [cm]",zaxis_title="y [cm]",aspectmode="data"),
                      margin=dict(l=0,r=0,t=35,b=0),title="3D view (interactive)")
    return fig


def truth_trajectory_overlay_diagnostic(trajectories):
    if trajectories is None:
        return False,"no trajectories table"
    if len(trajectories)==0:
        return False,"trajectories table is empty"
    names = trajectories.dtype.names or ()
    if all(k in names for k in ["x_start","y_start","z_start","x_end","y_end","z_end"]):
        return True,"using scalar start/end fields"
    if all(k in names for k in ["xyz_start","xyz_end"]):
        return True,"using vector xyz_start/xyz_end fields"
    return False,"missing trajectory coordinates (need scalar x/y/z start/end or xyz_start/xyz_end)"


def _trajectory_trace(trajectories):
    ok,_ = truth_trajectory_overlay_diagnostic(trajectories)
    if not ok:
        return None
    names = trajectories.dtype.names or ()
    if all(k in names for k in ["x_start","y_start","z_start","x_end","y_end","z_end"]):
        xs,ys,zs,xe,ye,ze = (trajectories[k].astype(float) for k in ["x_start","y_start","z_start","x_end","y_end","z_end"])
    else:
        start,end = np.asarray(trajectories["xyz_start"],dtype=float),np.asarray(trajectories["xyz_end"],dtype=float)
        if start.ndim!=2 or end.ndim!=2 or start.shape[1]<3 or end.shape[1]<3:
            return None
        xs,ys,zs = start[:,0],start[:,1],start[:,2]
        xe,ye,ze = end[:,0],end[:,1],end[:,2]
    x,y,z = [],[],[]
    for i in range(len(trajectories)):
        x += [float(zs[i]),float(ze[i]),None]
        y += [float(xs[i]),float(xe[i]),None]
        z += [float(ys[i]),float(ye[i]),None]
    return go.Scatter3d(x=x,y=y,z=z,mode="lines",line=dict(width=2,color="magenta"),name="Truth trajectories",opacity=0.55)


def make_plotly_analysis(hits,clusters=None):
    fig = make_subplots(rows=1,cols=2,subplot_titles=("Charge distribution","t_drift distribution"))
    if len(hits):
        q = hits["Q"].astype(float);q = q[np.isfinite(q)]
        fig.add_trace(go.Histogram(x=q,nbinsx=100,marker=dict(color="#4c78a8"),name="Q"),row=1,col=1)
        if "t_drift" in (hits.dtype.names or ()):
            td = hits["t_drift"].astype(float);td = td[np.isfinite(td)]
            fig.add_trace(go.Histogram(x=td,nbinsx=100,marker=dict(color="#f58518"),name="t_drift"),row=1,col=2)
    fig.update_xaxes(title_text="Q",row=1,col=1);fig.update_xaxes(title_text="t_drift",row=1,col=2)
    fig.update_yaxes(title_text="count",row=1,col=1);fig.update_yaxes(title_text="count",row=1,col=2)
    fig.update_layout(height=500,showlegend=False,margin=dict(l=10,r=10,t=40,b=10),title="Analysis")
    return fig
