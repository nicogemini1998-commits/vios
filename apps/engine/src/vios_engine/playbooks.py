"""Loader de playbooks (YAML → Playbook). STUB en M0: valida forma mínima."""
from pathlib import Path

import yaml
from vios_contracts import Playbook


def load_playbook(path: str | Path) -> Playbook:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Playbook(**data)
