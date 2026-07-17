"""Ejecución de ffmpeg — interfaz inyectable (patrón Transcoder de M3).

El plan es puro; aquí vive el único subprocess. Errores REPORTADOS, no
inventados: exit != 0 → RenderError con el final del stderr.
"""
from __future__ import annotations

import asyncio
from typing import Protocol

STDERR_TAIL_CHARS = 2000


class RenderError(RuntimeError):
    """ffmpeg falló o agotó el timeout."""


class FfmpegRunner(Protocol):
    async def run(self, args: list[str], timeout_s: float) -> None: ...


class SubprocessFfmpegRunner:
    def __init__(self, binary: str = "ffmpeg") -> None:
        self._binary = binary

    async def run(self, args: list[str], timeout_s: float) -> None:
        proc = await asyncio.create_subprocess_exec(
            self._binary, "-y", *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except TimeoutError as exc:
            proc.kill()
            await proc.wait()
            raise RenderError(f"ffmpeg superó el timeout de {timeout_s}s") from exc
        if proc.returncode != 0:
            tail = stderr.decode(errors="replace")[-STDERR_TAIL_CHARS:]
            raise RenderError(f"ffmpeg exit {proc.returncode}: {tail}")


class FakeFfmpegRunner:
    """Runner para tests: registra args y opcionalmente falla o escribe el output."""

    def __init__(self, fail_with: str = "", write_output: bool = True) -> None:
        self.calls: list[list[str]] = []
        self._fail_with = fail_with
        self._write_output = write_output

    async def run(self, args: list[str], timeout_s: float) -> None:
        self.calls.append(list(args))
        if self._fail_with:
            raise RenderError(self._fail_with)
        if self._write_output:
            from pathlib import Path

            Path(args[-1]).write_bytes(b"")
