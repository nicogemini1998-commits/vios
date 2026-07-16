"""Regenera schemas/timeline_ir.schema.json. Uso: uv run python scripts/export_schema.py"""
from pathlib import Path

from vios_contracts import export_json_schema

OUT = (
    Path(__file__).resolve().parents[1]
    / "src" / "vios_contracts" / "schemas" / "timeline_ir.schema.json"
)
export_json_schema(OUT)
print(f"schema escrito: {OUT}")
