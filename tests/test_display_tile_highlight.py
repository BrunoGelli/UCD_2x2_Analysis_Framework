import numpy as np
from ucd2x2.display.viz import (
    add_camera_spin,
    apply_detector_frame,
    color_array,
    detector_view_bounds,
    make_plotly_2d_projections,
    make_plotly_3d,
)


def _hits():
    a=np.zeros(5,dtype=[(f,'f8') for f in ('x','y','z','Q','t_drift','ts_pps')])
    a['x']=np.arange(5);a['Q']=[-3,0,1,10,100]
    return a


def test_no_tile_highlight_in_either_display():
    a=_hits()
    fig=make_plotly_3d(a,show_boxes=False)
    assert len(fig.data)==1
    assert all('Tile 5' not in (trace.name or '') for trace in fig.data)
    fig2=make_plotly_2d_projections(a)
    assert len(fig2.data)==4  # Three projections plus histogram; no tile edge traces.
    assert all('Tile 5' not in (trace.name or '') for trace in fig2.data)


def test_geometry_overlay_remains_available():
    assert len(make_plotly_3d(_hits(),show_boxes=True).data)==5


def test_nonpositive_charge_does_not_flatten_color_range():
    a=_hits();before=a.copy()
    colors,_=color_array(a,'Q')
    assert np.array_equal(colors,[0,0,0,1,2])
    assert np.array_equal(a,before)


def test_detector_frame_clamps_3d_and_all_spatial_2d_axes():
    a = _hits()
    # Deliberately absurd coordinate: it must not change framed detector bounds.
    a["x"][-1] = 5000
    fig3d = make_plotly_3d(a, show_boxes=True)
    fig2d = make_plotly_2d_projections(a)
    bounds = apply_detector_frame(fig3d, fig2d, padding_cm=2.0)

    assert bounds == detector_view_bounds(2.0)
    assert list(fig3d.layout.scene.xaxis.range) == bounds["z"]
    assert list(fig3d.layout.scene.yaxis.range) == bounds["x"]
    assert list(fig3d.layout.scene.zaxis.range) == bounds["y"]
    assert fig3d.layout.scene.aspectmode == "cube"

    assert list(fig2d.layout.xaxis.range) == bounds["x"]
    assert list(fig2d.layout.yaxis.range) == bounds["y"]
    assert list(fig2d.layout.xaxis2.range) == bounds["x"]
    assert list(fig2d.layout.yaxis2.range) == bounds["z"]
    assert list(fig2d.layout.xaxis3.range) == bounds["y"]
    assert list(fig2d.layout.yaxis3.range) == bounds["z"]


def test_camera_spin_adds_layout_only_play_pause_animation():
    fig = make_plotly_3d(_hits(), show_boxes=False)
    add_camera_spin(fig, seconds_per_rotation=12.0, n_frames=24)

    assert len(fig.frames) == 24
    assert all(len(frame.data) == 0 for frame in fig.frames)
    assert fig.frames[0].layout.scene.camera is not None
    menu = fig.layout.updatemenus[-1]
    assert [button.label for button in menu.buttons] == ["▶ Spin", "⏸ Pause"]
    assert all(button.method == "animate" for button in menu.buttons)
