import numpy as np
import pytest

from ucd2x2.display.video_export import (
    _camera_angles,
    choose_video_encoder,
    parse_event_indices,
)


def test_parse_event_indices_accepts_spaces_commas_and_deduplicates():
    assert parse_event_indices(["7,11", "11", "23"]) == [7, 11, 23]


def test_parse_event_indices_rejects_negative_and_invalid():
    with pytest.raises(ValueError, match="nonnegative"):
        parse_event_indices(["-1"])
    with pytest.raises(ValueError, match="Invalid event index"):
        parse_event_indices(["abc"])


def test_camera_angles_include_holds_and_half_turn():
    angles = _camera_angles(
        fps=10,
        seconds_per_event=2,
        hold_seconds=0.2,
        start_angle_deg=-30,
        rotation_degrees=180,
    )
    # 20 motion frames + 2 start hold + 2 end hold.
    assert len(angles) == 24
    assert np.isclose(angles[0], np.deg2rad(-30))
    assert np.isclose(angles[-1], np.deg2rad(150))
    assert np.isclose(angles[0], angles[1])
    assert np.isclose(angles[-1], angles[-2])


def test_choose_video_encoder_prefers_h264_for_mp4():
    assert choose_video_encoder("out.mp4", {"libx264", "libvpx-vp9"}) == "libx264"


def test_choose_video_encoder_reports_nersc_style_missing_h264():
    with pytest.raises(ValueError, match="libx264"):
        choose_video_encoder("out.mp4", {"libvpx-vp9"})


def test_choose_video_encoder_webm_fallback():
    assert choose_video_encoder("out.webm", {"libvpx-vp9"}) == "libvpx-vp9"
