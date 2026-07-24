from pathlib import Path

from ucd2x2.core.geometry import tile_5_iog_6_box_cm
from ucd2x2.core.io import FlowFile
from ucd2x2.display.viz import HIGHLIGHT_TILE_LABEL, make_plotly_2d_projections, make_plotly_3d


def _sample_hits():
    flow = FlowFile.open(str(Path(__file__).parent / "sample_data.hdf5"))
    try:
        return flow.get_event_hits(0).copy()
    finally:
        flow.close()


def test_event_display_draws_tile_5_iog_6_edge_in_3d_and_2d():
    hits = _sample_hits()
    fig_3d = make_plotly_3d(hits, show_boxes=False)
    fig_2d = make_plotly_2d_projections(hits)

    tile_box = tile_5_iog_6_box_cm()
    trace_3d = next(trace for trace in fig_3d.data if trace.name == HIGHLIGHT_TILE_LABEL)
    assert list(trace_3d.y[:2]) == [tile_box.xmin, tile_box.xmax]
    assert sum(trace.name == HIGHLIGHT_TILE_LABEL for trace in fig_2d.data) == 3
