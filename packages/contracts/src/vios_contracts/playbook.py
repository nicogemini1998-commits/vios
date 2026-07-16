"""Playbook — datos (YAML), no código (D7). STUB en M0 (detalle M2)."""
from pydantic import BaseModel, Field


class Playbook(BaseModel):
    schema_version: str = Field(default="0.0.1-stub")
    id: str
    name: str
    platform: str
    # M2: beats[], hook_specs, subtitulos, musica, ritmo, cta, duracion_ideal, metricas_objetivo
