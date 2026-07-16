"""Orquestación del análisis (M4): interfaces + analyze_asset + score heurístico.

Cero LLM en el core (D3). La visión con Claude es opcional e inyectable.
"""
from __future__ import annotations

from typing import Protocol

from vios_contracts import (
    EnergyPoint,
    Keyframe,
    MediaIntelligence,
    QualityScore,
    Scene,
    Silence,
    Transcript,
)

from ..media.models import AssetRecord


# --- puertos ---
class Transcriber(Protocol):
    def transcribe(self, audio_path: str, language: str | None = None) -> Transcript: ...


class SceneDetector(Protocol):
    def detect(self, video_path: str) -> list[Scene]: ...


class AudioAnalyzer(Protocol):
    def analyze(self, audio_path: str) -> tuple[list[EnergyPoint], list[Silence]]: ...


class FrameSampler(Protocol):
    def sample(self, scenes: list[Scene], duration_s: float | None = None) -> list[Keyframe]: ...


class VisionAnalyzer(Protocol):
    def describe(self, video_path: str, keyframes: list[Keyframe]) -> list[Keyframe]: ...


class IntelligenceCache(Protocol):
    def get(self, source_hash: str) -> MediaIntelligence | None: ...
    def put(self, source_hash: str, mi: MediaIntelligence) -> None: ...


# --- heurística de calidad ---
_MANY_SILENCES = 6
_SILENCE_RATIO = 0.4


def score_quality(
    asset: AssetRecord,
    transcript: Transcript,
    silences: list[Silence],
) -> QualityScore:
    notes: list[str] = []
    audio_ok = asset.meta.has_audio
    if not audio_ok:
        notes.append("El material no tiene pista de audio")
    if asset.meta.height and asset.meta.height < 720:
        notes.append(f"Resolucion baja ({asset.meta.height}p)")
    dur = asset.meta.duration_s or 0.0
    silent = sum(s.end_s - s.start_s for s in silences)
    if len(silences) >= _MANY_SILENCES or (dur and silent / dur > _SILENCE_RATIO):
        notes.append("Muchos silencios / ritmo lento en el bruto")
    if audio_ok and not transcript.segments:
        notes.append("Audio presente pero sin transcripcion (posible musica/ruido)")
    overall = 1.0 - 0.15 * len(notes)
    return QualityScore(overall=max(0.0, round(overall, 3)), audio_ok=audio_ok, notes=notes)


def analyze_asset(
    asset: AssetRecord,
    *,
    transcriber: Transcriber,
    scene_detector: SceneDetector,
    audio_analyzer: AudioAnalyzer,
    frame_sampler: FrameSampler,
    cache: IntelligenceCache,
    vision: VisionAnalyzer | None = None,
) -> MediaIntelligence:
    hit = cache.get(asset.hash)
    if hit is not None:                                   # D4: analizar una sola vez
        return hit

    video_src = asset.proxy_url or asset.original_url

    transcript = Transcript()
    energy: list[EnergyPoint] = []
    silences: list[Silence] = []
    if asset.meta.has_audio and asset.audio_url:
        transcript = transcriber.transcribe(asset.audio_url)
        energy, silences = audio_analyzer.analyze(asset.audio_url)

    scenes = scene_detector.detect(video_src)
    keyframes = frame_sampler.sample(scenes, asset.meta.duration_s)
    if vision is not None:
        keyframes = vision.describe(video_src, keyframes)

    quality = score_quality(asset, transcript, silences)

    mi = MediaIntelligence(
        asset_id=asset.id,
        source_hash=asset.hash,
        duration_s=asset.meta.duration_s,
        fps=asset.meta.fps,
        transcript=transcript,
        scenes=scenes,
        silences=silences,
        energy=energy,
        keyframes=keyframes,
        quality=quality,
    )
    cache.put(asset.hash, mi)
    return mi
