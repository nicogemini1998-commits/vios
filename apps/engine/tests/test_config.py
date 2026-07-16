"""T2 — config fail-fast: falta DATABASE_URL → ValidationError."""
import pytest
from pydantic import ValidationError
from vios_engine.config import Settings


def test_missing_required_raises(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # evitar que lea un .env real del cwd
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_present_ok(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    s = Settings(_env_file=None)
    assert s.database_url.startswith("postgresql://")
    assert s.engine_port == 8000
