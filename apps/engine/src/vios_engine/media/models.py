"""Modelos de almacenamiento de media (M3). Distinto de MediaIntelligence (M4)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class MediaMeta(BaseModel):
    duration_s: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    has_audio: bool = False
    codec: str = ""
    size_bytes: int | None = None
    mime: str = ""


class AssetRecord(BaseModel):
    id: str
    project_id: str
    hash: str
    original_url: str
    proxy_url: str = ""
    audio_url: str | None = None
    meta: MediaMeta = Field(default_factory=MediaMeta)
    status: str = "ready"        # ready | error
    error: str = ""
