import panel as pn

from twobytwo_display.stage2.cuts import DBSCANClusterProducer
from twobytwo_display.stage2.pipeline import ParamSpec
from twobytwo_display.stage2.widgets import widget_from_param_spec, widgets_from_param_specs


def test_widget_from_param_spec_float():
    ps = ParamSpec("eps_cm", 1.5, label="DBSCAN eps [cm]", kind="float", step=0.1)
    w = widget_from_param_spec(ps)
    assert isinstance(w, pn.widgets.FloatInput)


def test_widget_from_param_spec_int():
    ps = ParamSpec("min_samples", 10, label="DBSCAN min_samples", kind="int", step=1)
    w = widget_from_param_spec(ps)
    assert isinstance(w, pn.widgets.IntInput)


def test_dbscan_param_specs_convert_to_widgets():
    widgets = widgets_from_param_specs(DBSCANClusterProducer.param_specs)
    assert set(widgets) == {"eps_cm", "min_samples", "cluster_min_hits", "cluster_max_extent_cm"}
