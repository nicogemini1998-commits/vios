"""T4: validación semántica (CL1-CL4)."""
import pytest
from builders import base_ir
from vios_contracts import TimelineDraft, TimelineValidationError, validate


def test_t4_empty_is_valid():  # CL4
    validate(base_ir())


def test_t4_out_le_in_rejected():  # CL1
    d = TimelineDraft.from_ir(base_ir())
    vt = d.add_track("video")
    d.add_clip(vt, source="a", start=0, in_point=100, out_point=100)
    with pytest.raises(TimelineValidationError):
        d.commit(by="t", why="bad")


def test_t4_negative_frames_rejected():  # CL3
    d = TimelineDraft.from_ir(base_ir())
    vt = d.add_track("video")
    d.add_clip(vt, source="a", start=-5, in_point=0, out_point=30)
    with pytest.raises(TimelineValidationError):
        d.commit(by="t", why="bad")


def test_t4_clip_on_missing_track_rejected():  # CL2
    d = TimelineDraft.from_ir(base_ir())
    with pytest.raises(KeyError):
        d.add_clip("nope", source="a", start=0, in_point=0, out_point=30)
