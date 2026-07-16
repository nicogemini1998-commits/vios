"""VIOS media pipeline (M3): ingesta upload→Storage→proxy→hash-cache."""
from .hashing import sha256_file
from .models import AssetRecord, MediaMeta
from .pipeline import IngestResult, ingest_media
from .probe import FfprobeProber, MediaProber, ProbeError
from .repo import AssetRepo, InMemoryAssetRepo
from .storage import LocalStorage, StorageBackend
from .transcode import FfmpegTranscoder, TranscodeError, Transcoder

__all__ = [
    "AssetRecord", "MediaMeta", "sha256_file",
    "StorageBackend", "LocalStorage",
    "MediaProber", "FfprobeProber", "ProbeError",
    "Transcoder", "FfmpegTranscoder", "TranscodeError",
    "AssetRepo", "InMemoryAssetRepo",
    "IngestResult", "ingest_media",
]
