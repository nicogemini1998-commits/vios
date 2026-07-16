"""T1 — /health y /version responden (db puede estar down en unit test)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/nodb")
    from vios_engine.main import app

    return TestClient(app)


def test_version(client):
    r = client.get("/version")
    assert r.status_code == 200
    assert r.json()["service"] == "vios-engine"


def test_health_shape(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert "db" in body["deps"]
