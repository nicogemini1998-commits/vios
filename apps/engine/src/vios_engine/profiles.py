"""Loader de fichas de cliente (YAML → ClientProfile)."""
from pathlib import Path

import yaml
from vios_contracts import ClientProfile


def load_client(path: str | Path) -> ClientProfile:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return ClientProfile(**data)


def load_clients_dir(directory: str | Path) -> dict[str, ClientProfile]:
    """Carga todos los *.yaml de un directorio, indexados por client_id."""
    out: dict[str, ClientProfile] = {}
    for p in sorted(Path(directory).glob("*.yaml")):
        cp = load_client(p)
        out[cp.client_id] = cp
    return out
