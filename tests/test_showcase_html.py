import plotly.graph_objects as go

from ucd2x2.display.showcase_html import export_showcase_html


def test_showcase_html_contains_multiple_events_and_smooth_rotation(tmp_path):
    def event(index):
        fig3d = go.Figure(go.Scatter3d(
            x=[0, 1, 2], y=[0, 1, 2], z=[0, 1, 2], mode="markers",
            marker=dict(
                color=[0.0, 1.0, 2.0],
                colorscale="Viridis",
                cauto=False,
                cmin=0.0,
                cmax=2.0,
                showscale=True,
            ),
        ))
        fig2d = go.Figure(go.Scatter(
            x=[0, 1, 2], y=[2, 1, 0], mode="markers",
            marker=dict(
                color=[0.0, 1.0, 2.0],
                colorscale="Viridis",
                cauto=False,
                cmin=0.0,
                cmax=2.0,
            ),
        ))
        return {
            "event_index": index,
            "event_id": 1000 + index,
            "fig3d": fig3d,
            "fig2d": fig2d,
            "metadata": {
                "event_summary": {"total_Q": 42.0, "n_unique_pixels": 3},
                "cleaning_report": {"clean_hits": 3},
            },
        }

    output = tmp_path / "showcase.html"
    saved = export_showcase_html(
        output,
        title="2x2 selected events",
        subtitle="cold commissioning",
        events=[event(7), event(11)],
        seconds_per_rotation=18,
    )

    text = saved.read_text()
    assert saved == output.resolve()
    assert "Event 7" in text
    assert "Event 11" in text
    assert "Orthogonal projections" in text
    assert "Technical details" in text
    assert "requestAnimationFrame" in text
    assert "Plotly.relayout" in text
    assert "minFrameMs=33" in text
    assert '"cauto":false' in text
    assert '"color":[0.0,1.0,2.0]' in text
