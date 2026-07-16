"""ingest_media — orquesta hash-cache (D4), storage por URL (D6), proxy y audio."""
from __future__ import annotations

import uuid
from pathlib import Path

from pydantic import BaseModel

from .hashing import sha256_file
from .models import AssetRecord
from .probe import MediaProber, ProbeError
from .repo import AssetRepo
from .storage import StorageBackend
from .transcode import TranscodeError, Transcoder


class IngestResult(BaseModel):
    record: AssetRecord
    cached: bool


def ingest_media(
    project_id: str,
    source: str | Path,
    *,
    storage: StorageBackend,
    prober: MediaProber,
    transcoder: Transcoder,
    repo: AssetRepo,
    proxy_height: int = 480,
) -> IngestResult:
    source = Path(source)
    file_hash = sha256_file(source)

    cached = repo.find_by_hash(file_hash)
    if cached is not None:                       # D4: analizar/almacenar una sola vez
        return IngestResult(record=cached, cached=True)

    ext = source.suffix or ".bin"
    original_url = storage.put(source, f"{file_hash}/original{ext}")
    asset_id = uuid.uuid4().hex

    # metadata (si falla → asset en error, sin inventar; manual §2)
    try:
        meta = prober.probe(source)
    except ProbeError as exc:
        record = AssetRecord(
            id=asset_id, project_id=project_id, hash=file_hash,
            original_url=original_url, status="error", error=str(exc),
        )
        repo.add(record)
        return IngestResult(record=record, cached=False)

    proxy_url = ""
    audio_url: str | None = None
    try:
        proxy_local = source.with_name(f"{file_hash}_proxy.mp4")
        transcoder.make_proxy(source, proxy_local, height=proxy_height)
        proxy_url = storage.put(proxy_local, f"{file_hash}/proxy_{proxy_height}.mp4")

        if meta.has_audio:
            audio_local = source.with_name(f"{file_hash}_audio.wav")
            transcoder.extract_audio(source, audio_local)
            audio_url = storage.put(audio_local, f"{file_hash}/audio.wav")
    except TranscodeError as exc:
        record = AssetRecord(
            id=asset_id, project_id=project_id, hash=file_hash,
            original_url=original_url, meta=meta, status="error", error=str(exc),
        )
        repo.add(record)
        return IngestResult(record=record, cached=False)

    record = AssetRecord(
        id=asset_id, project_id=project_id, hash=file_hash,
        original_url=original_url, proxy_url=proxy_url, audio_url=audio_url,
        meta=meta, status="ready",
    )
    repo.add(record)
    return IngestResult(record=record, cached=False)
