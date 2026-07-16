"""T4 — loader lee el YAML de ejemplo sin error."""
from pathlib import Path

from vios_engine.playbooks import load_playbook

ROOT = Path(__file__).resolve().parents[3]


def test_load_example_playbook():
    pb = load_playbook(ROOT / "playbooks" / "reel-educativo.example.yaml")
    assert pb.id == "reel-educativo"
    assert pb.platform == "instagram"
