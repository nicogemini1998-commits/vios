"""T1-T3, T5-T6: creación, draft/commit, inmutabilidad, diff, round-trip."""
import pytest
from builders import base_ir, build_reel
from pydantic import ValidationError
from vios_contracts import TimelineDraft, diff, from_json, to_json, validate


def test_t1_create_empty():
    ir = base_ir()
    assert ir.revision == 0
    assert ir.parent_revision is None
    assert ir.tracks == []
    assert ir.schema_version == "1.0.0"
    validate(ir)  # no lanza


def test_t2_commit_new_revision_and_decision():
    ir0 = base_ir()
    ir1 = build_reel()
    assert ir1.revision == 1
    assert ir1.parent_revision == 0
    assert len(ir1.tracks) == 2
    assert ir1.meta.decisions[-1].agent == "edit-agent"
    assert ir1.meta.decisions[-1].revision == 1
    # IR base intacta (inmutabilidad de la revisión previa)
    assert ir0.revision == 0 and ir0.tracks == []


def test_t2_deterministic_ids():
    ir = build_reel()
    assert [t.id for t in ir.tracks] == ["v0", "s0"]
    assert [c.id for c in ir.tracks[0].clips] == ["c0", "c1"]
    assert [m.id for m in ir.markers] == ["m0"]


def test_t3_immutability_frozen():
    ir = base_ir()
    with pytest.raises(ValidationError):
        ir.revision = 99  # frozen


def test_t2_chained_revisions_keep_id_sequence():
    ir1 = build_reel()
    d = TimelineDraft.from_ir(ir1)
    tid = d.add_track("audio")
    ir2 = d.commit(by="audio-agent", why="add music track")
    assert ir2.revision == 2 and ir2.parent_revision == 1
    assert tid == "a0"  # no colisiona con ids previos
    assert len(ir2.meta.decisions) == 2


def test_t5_diff():
    ir0 = base_ir()
    ir1 = build_reel()
    changes = diff(ir0, ir1)
    paths = {c.path for c in changes}
    assert "tracks/v0" in paths
    assert "tracks/s0" in paths
    assert "markers/m0" in paths
    assert all(c.op == "add" for c in changes)
    assert diff(ir1, ir1) == []


def test_t6_json_round_trip():
    ir = build_reel()
    restored = from_json(to_json(ir))
    assert restored == ir
