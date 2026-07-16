"""T7: export JSON Schema y verificación de que el fichero versionado está al día."""
import json
from pathlib import Path

from vios_contracts import TimelineIR, export_json_schema

SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "vios_contracts" / "schemas" / "timeline_ir.schema.json"
)


def test_t7_schema_has_expected_keys():
    schema = TimelineIR.model_json_schema()
    props = schema["properties"]
    for key in ("tracks", "markers", "meta", "schema_version", "fps", "canvas"):
        assert key in props


def test_t7_versioned_schema_up_to_date(tmp_path):
    tmp = tmp_path / "s.json"
    export_json_schema(tmp)
    fresh = json.loads(tmp.read_text())
    stored = json.loads(SCHEMA_PATH.read_text())
    assert fresh == stored, "schema versionado desfasado: corre scripts/export_schema.py"
