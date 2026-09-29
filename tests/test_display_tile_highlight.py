import numpy as np
from ucd2x2.display.viz import make_plotly_3d,make_plotly_2d_projections,color_array


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
