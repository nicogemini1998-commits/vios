"""Cobertura de ramas: remove_*, diff modify/remove, validaciones restantes."""
import pytest
from builders import base_ir, build_reel
from vios_contracts import (
    Canvas,
    Meta,
    TimelineDraft,
    TimelineIR,
    TimelineValidationError,
    diff,
    validate,
)


def test_remove_clip_track_marker():
    d = TimelineDraft.from_ir(build_reel())
    d.remove_clip("v0", "c1")
    d.remove_marker("m0")
    ir = d.commit(by="t", why="cleanup")
    assert [c.id for c in ir.tracks[0].clips] == ["c0"]
    assert ir.markers == []
    d2 = TimelineDraft.from_ir(ir)
    d2.remove_track("v0")
    ir2 = d2.commit(by="t", why="drop video")
    assert [t.id for t in ir2.tracks] == ["s0"]


def test_diff_modify_and_remove():
    ir1 = build_reel()
    d = TimelineDraft.from_ir(ir1)
    d.remove_marker("m0")
    ir2 = d.commit(by="t", why="quita hook")
    changes = {c.op for c in diff(ir1, ir2)}
    assert "remove" in changes

    d3 = TimelineDraft.from_ir(ir1)
    d3.add_marker("cta", at=120, label="nuevo")
    ir3 = d3.commit(by="t", why="add cta")
    # meta.decisions cambia pero markers añade → detecta add
    assert any(c.op == "add" and c.path.startswith("markers/") for c in diff(ir1, ir3))


def test_validate_marker_negative():
    d = TimelineDraft.from_ir(base_ir())
    d.add_marker("beat", at=-1)
    with pytest.raises(TimelineValidationError):
        d.commit(by="t", why="bad")


def _mk(**over):
    kw = dict(
        project_id="p", fps=30,
        canvas=Canvas(width=1080, height=1920, aspect="9:16"),
        meta=Meta(platform="ig", playbook="pb"),
    )
    kw.update(over)
    return TimelineIR(**kw)


def test_validate_fps_canvas_parent():
    with pytest.raises(TimelineValidationError):
        validate(_mk(fps=0))
    with pytest.raises(TimelineValidationError):
        validate(_mk(canvas=Canvas(width=0, height=10, aspect="x")))
    with pytest.raises(TimelineValidationError):
        validate(_mk(revision=1, parent_revision=1))


def test_validate_duplicate_ids():
    from vios_contracts import Clip, Track
    ir = _mk(tracks=[
        Track(id="v0", kind="video", clips=[
            Clip(id="c0", source="a", start=0, in_point=0, out_point=30),
            Clip(id="c0", source="b", start=30, in_point=0, out_point=30),
        ])
    ])
    with pytest.raises(TimelineValidationError):
        validate(ir)
