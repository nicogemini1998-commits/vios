"""Contratos importan e instancian objetos válidos.

TimelineIR (M1), ClientProfile + Playbook (M2) son reales; MediaIntelligence sigue stub.
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


def test_client_and_playbook_real():
    cp = ClientProfile(client_id="c1", name="Cliender")
    pb = Playbook(id="reel-edu", name="Reel", platforms=["instagram"])
    assert cp.schema_version == "1.0.0"
    assert pb.schema_version == "1.0.0"


def test_media_intelligence_stub():
    mi = MediaIntelligence(asset_id="a1", source_hash="deadbeef")
    assert mi.schema_version.endswith("stub")
