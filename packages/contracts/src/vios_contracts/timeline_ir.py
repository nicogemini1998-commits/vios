"""Timeline IR (D1) — contrato central de VIOS.

Representación intermedia declarativa de una edición. Frame-based (determinista),
inmutable por revisión, auditable (cada revisión anota quién y por qué).

Time unit canónico = FRAMES (int). `fps` en la raíz convierte a segundos en render.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"

TrackKind = Literal["video", "audio", "subtitle", "graphic"]
MarkerKind = Literal["beat", "hook", "cta"]

# prefijo de id determinista por tipo (RF4)
_KIND_PREFIX: dict[str, str] = {
    "video": "v",
    "audio": "a",
    "subtitle": "s",
    "graphic": "g",
}


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class Canvas(_Frozen):
    width: int
    height: int
    aspect: str  # ej. "9:16", "1:1", "16:9"


class Transform(_Frozen):
    scale: float = 1.0
    x: int = 0
    y: int = 0
    rotation: float = 0.0
    opacity: float = 1.0


class Effect(_Frozen):
    type: str
    params: dict[str, Any] = Field(default_factory=dict)


class Clip(_Frozen):
    id: str
    source: str                 # asset_id (video/audio) o texto/ref (subtitle/graphic)
    start: int                  # frame de inicio en la timeline
    in_point: int               # recorte dentro del source (frame)
    out_point: int              # recorte dentro del source (frame); duracion = out-in
    transform: Transform = Field(default_factory=Transform)
    effects: list[Effect] = Field(default_factory=list)


class Track(_Frozen):
    id: str
    kind: TrackKind
    clips: list[Clip] = Field(default_factory=list)


class Marker(_Frozen):
    id: str
    kind: MarkerKind
    at: int                     # frame
    label: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class Decision(_Frozen):
    """Entrada de auditoría append-only: quién cambió la IR y por qué."""
    revision: int
    agent: str
    why: str
    action: str = ""


class Meta(_Frozen):
    platform: str
    playbook: str
    decisions: list[Decision] = Field(default_factory=list)


class TimelineIR(_Frozen):
    schema_version: str = SCHEMA_VERSION
    project_id: str
    revision: int = 0
    parent_revision: int | None = None
    fps: int
    canvas: Canvas
    tracks: list[Track] = Field(default_factory=list)
    markers: list[Marker] = Field(default_factory=list)
    meta: Meta
    id_seq: dict[str, int] = Field(default_factory=dict)  # contadores id deterministas


def kind_prefix(kind: str) -> str:
    """Prefijo de id para un TrackKind. Lanza KeyError si el kind es desconocido."""
    return _KIND_PREFIX[kind]


def create_timeline(
    project_id: str,
    fps: int,
    canvas: Canvas,
    platform: str,
    playbook: str,
) -> TimelineIR:
    """Crea una IR vacía válida en revisión 0 (RF1)."""
    from .timeline_ops import validate

    ir = TimelineIR(
        project_id=project_id,
        fps=fps,
        canvas=canvas,
        revision=0,
        parent_revision=None,
        meta=Meta(platform=platform, playbook=playbook),
    )
    validate(ir)
    return ir
