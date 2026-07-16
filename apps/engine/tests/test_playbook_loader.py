"""Loader lee los playbooks semilla y valida el schema real (M2)."""
from pathlib import Path

from vios_engine.playbooks import load_playbook, load_playbooks_dir

ROOT = Path(__file__).resolve().parents[3]
PB_DIR = ROOT / "playbooks"


def test_load_reel_educativo():
    pb = load_playbook(PB_DIR / "reel-educativo.yaml")
    assert pb.id == "reel-educativo"
    assert "instagram" in pb.platforms
    assert pb.hook.max_seconds == 3.0


def test_load_playbooks_dir_indexes_by_id():
    pbs = load_playbooks_dir(PB_DIR)
    assert set(pbs) == {"reel-educativo", "podcast-clips"}
