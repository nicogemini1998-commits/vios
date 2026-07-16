"""Transcodificación con FFmpeg: proxy 480p + extracción de audio."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol


class TranscodeError(RuntimeError):
    """FFmpeg falló durante proxy o extracción de audio."""


class Transcoder(Protocol):
    def make_proxy(self, src: str | Path, dst: str | Path, height: int = 480) -> None: ...
    def extract_audio(self, src: str | Path, dst: str | Path) -> None: ...


class FfmpegTranscoder:
    def __init__(self, ffmpeg_bin: str = "ffmpeg") -> None:
        self.bin = ffmpeg_bin

    def _run(self, args: list[str]) -> None:
        cmd = [self.bin, "-y", "-hide_banner", "-loglevel", "error", *args]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise TranscodeError(f"ffmpeg fallo: {exc}") from exc

    def make_proxy(self, src: str | Path, dst: str | Path, height: int = 480) -> None:
        # scale=-2:H conserva aspect (vertical/horizontal), ancho par para H.264
        self._run([
            "-i", str(src),
            "-vf", f"scale=-2:{height}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
            "-c:a", "aac", "-b:a", "128k",
            str(dst),
        ])

    def extract_audio(self, src: str | Path, dst: str | Path) -> None:
        self._run([
            "-i", str(src), "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1", str(dst),
        ])
