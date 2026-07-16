"""T3 — los 4 contratos stub importan e instancian un objeto ejemplo válido."""
from vios_contracts import ClientProfile, MediaIntelligence, Playbook, TimelineIR


def test_instantiate_stubs():
    ir = TimelineIR(project_id="p1")
    cp = ClientProfile(client_id="c1", name="Cliender")
    pb = Playbook(id="reel-edu", name="Reel educativo", platform="instagram")
    mi = MediaIntelligence(asset_id="a1", source_hash="deadbeef")
    for obj in (ir, cp, pb, mi):
        assert obj.schema_version.endswith("stub")
    assert ir.revision == 0
