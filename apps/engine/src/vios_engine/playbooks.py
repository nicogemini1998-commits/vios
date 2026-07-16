"""Loader de playbooks (YAML → Playbook), con validación semántica."""
from pathlib import Path

import yaml
from vios_contracts import Playbook, validate_playbook


def load_playbook(path: str | Path) -> Playbook:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    pb = Playbook(**data)
    validate_playbook(pb)
    return pb


def load_playbooks_dir(directory: str | Path) -> dict[str, Playbook]:
    """Carga todos los *.yaml de un directorio, indexados por id. Ignora subdirs."""
    out: dict[str, Playbook] = {}
    for p in sorted(Path(directory).glob("*.yaml")):
        pb = load_playbook(p)
        out[pb.id] = pb
    return out
