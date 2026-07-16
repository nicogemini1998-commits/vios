"""Playbook — estilo/estrategia de edición como DATO (D7), no código.

Estructura narrativa (beats con duración relativa), hook, políticas de subtítulos/
música/ritmo/CTA, duración ideal por plataforma y métricas objetivo.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Beat(_Model):
    name: str
    rel_duration: float           # fracción del total (los beats suman ~1.0)
    purpose: str = ""


class HookSpec(_Model):
    max_seconds: float
    style: str = ""
    land_by_seconds: float = 3.0


class SubtitlePolicy(_Model):
    enabled: bool = True
    karaoke: bool = False
    emphasis: bool = True
    uppercase: bool = False


class MusicPolicy(_Model):
    enabled: bool = True
    style: str = ""
    ducking: bool = True
    target_lufs: float = -14.0


class PacingPolicy(_Model):
    cut_style: str = "medium"     # calm | medium | aggressive
    zoom: bool = False
    energy: str = "medium"


class CTAPolicy(_Model):
    enabled: bool = True
    position: str = "end"         # start | mid | end
    default_text: str = ""


class DurationRange(_Model):
    min_s: float
    max_s: float


class Playbook(_Model):
    schema_version: str = SCHEMA_VERSION
    id: str
    name: str
    platforms: list[str] = Field(default_factory=list)
    beats: list[Beat] = Field(default_factory=list)
    hook: HookSpec | None = None
    subtitles: SubtitlePolicy | None = None
    music: MusicPolicy | None = None
    pacing: PacingPolicy | None = None
    cta: CTAPolicy | None = None
    ideal_duration: dict[str, DurationRange] = Field(default_factory=dict)
    target_metrics: dict[str, float] = Field(default_factory=dict)


class PlaybookValidationError(ValueError):
    """El playbook viola una regla semántica (beats mal normalizados, etc.)."""


def validate_playbook(pb: Playbook) -> None:
    """Valida semántica del playbook (RF5). Lanza PlaybookValidationError."""
    if pb.beats:
        total = sum(b.rel_duration for b in pb.beats)
        if abs(total - 1.0) > 0.01:
            raise PlaybookValidationError(
                f"beats deben sumar ~1.0, suman {total:.3f}"
            )
        for b in pb.beats:
            if b.rel_duration <= 0:
                raise PlaybookValidationError(f"beat '{b.name}': rel_duration debe ser > 0")
    if pb.hook is not None and pb.hook.max_seconds <= 0:
        raise PlaybookValidationError("hook.max_seconds debe ser > 0")
    for platform, rng in pb.ideal_duration.items():
        if rng.min_s > rng.max_s:
            raise PlaybookValidationError(f"ideal_duration[{platform}]: min_s > max_s")
