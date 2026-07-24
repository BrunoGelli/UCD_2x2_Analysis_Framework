from pathlib import Path

from ucd2x2.core.io import FlowFile
from ucd2x2.display.viz import HIGHLIGHT_LABEL, make_plotly_2d_projections, make_plotly_3d


def _sample_hits_with_tile_5_iog_6():
    flow = FlowFile.open(str(Path(__file__).parent / "sample_data.hdf5"))
    try:
        for event_index in range(flow.n_events()):
            hits = flow.get_event_hits(event_index)
            if ((hits["io_group"] == 6) & (hits["io_channel"] == 5)).any():
                return hits.copy()
    finally:
        flow.close()
    raise AssertionError("sample fixture has no hits for tile 5 on IOG 6")


def test_event_display_highlights_tile_5_on_iog_6_in_3d_and_2d():
    hits = _sample_hits_with_tile_5_iog_6()

    fig_3d = make_plotly_3d(hits, max_hits=1, show_boxes=False)
    fig_2d = make_plotly_2d_projections(hits, max_hits=1)

    assert any(trace.name == HIGHLIGHT_LABEL for trace in fig_3d.data)
    assert sum(trace.name == HIGHLIGHT_LABEL for trace in fig_2d.data) == 3
