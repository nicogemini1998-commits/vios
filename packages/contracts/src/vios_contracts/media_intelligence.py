"""MediaIntelligence (M4) — análisis cacheado por asset (D4).

Unidades en SEGUNDOS (dominio de análisis, relativo al source). La conversión a
frames la hace el Edit Agent con `fps` (frontera con Timeline IR).
Transcript = salida literal de Whisper; tramos dudosos se marcan low_confidence,
nunca se inventa texto (manual VIOS §2.1/§2.3).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Word(_Model):
    start_s: float
    end_s: float
    text: str
    prob: float = 1.0


class Segment(_Model):
    start_s: float
    end_s: float
    text: str
    low_confidence: bool = False
    words: list[Word] = Field(default_factory=list)


class Transcript(_Model):
    language: str = ""
    segments: list[Segment] = Field(default_factory=list)


class Scene(_Model):
    index: int
    start_s: float
    end_s: float


class Silence(_Model):
    start_s: float
    end_s: float


class EnergyPoint(_Model):
    at_s: float
    rms: float


class Keyframe(_Model):
    at_s: float
    scene_index: int
    description: str = ""      # opcional, lo rellena VisionAnalyzer (Claude) si se inyecta


class QualityScore(_Model):
    overall: float = 1.0
    audio_ok: bool = True
    notes: list[str] = Field(default_factory=list)


class MediaIntelligence(_Model):
    schema_version: str = SCHEMA_VERSION
    asset_id: str
    source_hash: str
    duration_s: float | None = None
    fps: float | None = None
    transcript: Transcript = Field(default_factory=Transcript)
    scenes: list[Scene] = Field(default_factory=list)
    silences: list[Silence] = Field(default_factory=list)
    energy: list[EnergyPoint] = Field(default_factory=list)
    keyframes: list[Keyframe] = Field(default_factory=list)
    quality: QualityScore = Field(default_factory=QualityScore)
