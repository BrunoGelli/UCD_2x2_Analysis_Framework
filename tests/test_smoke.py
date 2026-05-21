import importlib
from pathlib import Path

from ucd2x2.core.io import FlowFile


def test_main_modules_importable():
    modules = [
        "ucd2x2.display.app_panel",
        "ucd2x2.core.io",
        "ucd2x2.display.viz",
        "ucd2x2.core.clustering",
        "ucd2x2.core.geometry",
    ]
    for module_name in modules:
        importlib.import_module(module_name)


def test_flowfile_opens_sample_and_reads_first_event_prompt_hits():
    sample_h5 = Path(__file__).parent / "sample_data.hdf5"
    ff = FlowFile.open(str(sample_h5))
    try:
        assert ff.h5 is not None
        assert ff.n_events() > 0
        ff.get_event_hits(0, hit_type="prompt")
    finally:
        ff.close()
