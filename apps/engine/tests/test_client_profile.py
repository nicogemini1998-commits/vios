"""M2 T1-T4, T7-T8: ficha cliente, gate de completitud, branding real."""
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from vios_contracts import ClientProfile, client_missing_blocks, is_client_editable
from vios_engine.profiles import load_client, load_clients_dir

ROOT = Path(__file__).resolve().parents[3]
CLIENTS = ROOT / "playbooks" / "clients"
SEED = CLIENTS / "cliender.yaml"


def test_t1_cliender_seed_editable():
    cp = load_client(SEED)
    assert client_missing_blocks(cp) == []
    assert is_client_editable(cp) is True


def test_t2_brand_tokens_are_official():
    cp = load_client(SEED)
    hexes = {c.hex for c in cp.visual.palette}
    assert {"#8F7EE9", "#1E2839", "#14181E", "#EBEAE4", "#FFFFFF"} <= hexes
    families = {f.family for f in cp.visual.fonts}
    assert {"Manrope", "Inconsolata"} <= families


def test_t3_incomplete_profile_not_editable():
    data = yaml.safe_load(SEED.read_text(encoding="utf-8"))
    data.pop("visual")        # quita bloque B
    data.pop("audience")      # quita bloque D
    cp = ClientProfile(**data)
    missing = client_missing_blocks(cp)
    assert is_client_editable(cp) is False
    assert any("B.visual" in m for m in missing)
    assert any("D.audience" in m for m in missing)


def test_t4_invalid_hex_rejected():
    with pytest.raises(ValidationError):
        ClientProfile(
            client_id="x", name="X",
            visual={"palette": [{"name": "bad", "hex": "#GGGGGG", "role": "primary"}], "fonts": []},
        )


def test_t4_invalid_treatment_rejected():
    with pytest.raises(ValidationError):
        ClientProfile(client_id="x", name="X", voice={"treatment": "vos"})


def test_t7_load_clients_dir():
    clients = load_clients_dir(CLIENTS)
    assert "cliender" in clients


def test_t8_round_trip():
    cp = load_client(SEED)
    again = ClientProfile(**cp.model_dump())
    assert again == cp
