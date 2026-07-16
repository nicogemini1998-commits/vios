"""Contratos importan e instancian objetos válidos.

TimelineIR es real desde M1; ClientProfile/Playbook/MediaIntelligence siguen stub.
"""
from vios_contracts import (
    Canvas,
    ClientProfile,
    MediaIntelligence,
    Playbook,
    TimelineIR,
    create_timeline,
)


def test_timeline_ir_real():
    ir = create_timeline(
        project_id="p1", fps=30,
        canvas=Canvas(width=1080, height=1920, aspect="9:16"),
        platform="instagram", playbook="reel-educativo",
    )
    assert isinstance(ir, TimelineIR)
    assert ir.schema_version == "1.0.0"
    assert ir.revision == 0


def test_remaining_stubs():
    cp = ClientProfile(client_id="c1", name="Cliender")
    pb = Playbook(id="reel-edu", name="Reel", platform="instagram")
    mi = MediaIntelligence(asset_id="a1", source_hash="deadbeef")
    for obj in (cp, pb, mi):
        assert obj.schema_version.endswith("stub")
