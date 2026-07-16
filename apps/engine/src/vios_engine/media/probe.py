"""Sondeo de metadata con ffprobe (parseo JSON, no regex)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Protocol

from .models import MediaMeta


class ProbeError(RuntimeError):
    """ffprobe falló o el archivo no es media reconocible."""


class MediaProber(Protocol):
    def probe(self, path: str | Path) -> MediaMeta: ...


def _parse_fps(rate: str) -> float | None:
    # ffprobe da "30000/1001" o "25/1"
    try:
        num, den = rate.split("/")
        den_f = float(den)
        return round(float(num) / den_f, 3) if den_f else None
    except (ValueError, ZeroDivisionError):
        return None


class FfprobeProber:
    def __init__(self, ffprobe_bin: str = "ffprobe") -> None:
        self.bin = ffprobe_bin

    def probe(self, path: str | Path) -> MediaMeta:
        cmd = [
            self.bin, "-v", "error", "-show_format", "-show_streams",
            "-of", "json", str(path),
        ]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise ProbeError(f"ffprobe fallo en {path}: {exc}") from exc

        try:
            data = json.loads(out.stdout)
        except json.JSONDecodeError as exc:
            raise ProbeError(f"salida ffprobe no-JSON: {exc}") from exc

        streams = data.get("streams", [])
        fmt = data.get("format", {})
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

        duration = fmt.get("duration") or (video or {}).get("duration")
        size = fmt.get("size")
        return MediaMeta(
            duration_s=float(duration) if duration else None,
            width=int(video["width"]) if video and video.get("width") else None,
            height=int(video["height"]) if video and video.get("height") else None,
            fps=(_parse_fps(video["avg_frame_rate"])
                 if video and video.get("avg_frame_rate") else None),
            has_audio=audio is not None,
            codec=(video or {}).get("codec_name", ""),
            size_bytes=int(size) if size else None,
            mime=fmt.get("format_name", ""),
        )
