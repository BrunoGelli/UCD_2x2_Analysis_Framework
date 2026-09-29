import plotly.graph_objects as go

from ucd2x2.display.export_html import export_event_html
from ucd2x2.display.viz import add_camera_spin


def test_export_event_html_is_self_contained_and_keeps_spin(tmp_path):
    fig3d = go.Figure(go.Scatter3d(
        x=[0, 1, 2], y=[0, 1, 2], z=[0, 1, 2], mode="markers",
        marker=dict(
            color=[0.0, 1.0, 2.0], colorscale="Viridis",
            cauto=False, cmin=0.0, cmax=2.0, showscale=True,
        ),
    ))
    add_camera_spin(fig3d, seconds_per_rotation=8.0, n_frames=12)
    fig2d = go.Figure(go.Scatter(x=[0, 1], y=[1, 0]))
    analysis = go.Figure(go.Histogram(x=[1, 2, 2, 3]))

    output = tmp_path / "event.html"
    saved = export_event_html(
        output,
        title="2x2 test event",
        metadata={"event_index": 7, "view": "cleaned"},
        fig3d=fig3d,
        fig2d=fig2d,
        analysis=analysis,
    )

    text = saved.read_text()
    assert saved == output.resolve()
    assert "2x2 test event" in text
    assert '"event_index": 7' in text
    assert "plotly.js" in text.lower() or "plotly-" in text.lower()
    assert "camera-spin-" in text
    assert "Spin" in text
    assert '"cauto":false' in text
    assert '"cmin":0.0' in text
    assert '"cmax":2.0' in text
    assert '"color":[0.0,1.0,2.0]' in text
