"""Timeline IR (D1) — contrato central del sistema. STUB en M0.

El diseño real (tracks, clips, markers, decisions auditables) llega en M1.
Aquí solo reservamos el tipo y el campo de versión para poder importarlo.
"""
from pydantic import BaseModel, Field


class TimelineIR(BaseModel):
    schema_version: str = Field(default="0.0.1-stub")
    project_id: str
    revision: int = 0
    # M1: fps, canvas, tracks[], clips[], markers[], meta{}
