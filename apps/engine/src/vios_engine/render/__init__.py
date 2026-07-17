"""Render FFmpeg nativo (M11) — IR → filtergraph → preview/masters/thumbnail."""
from .masters import PLATFORM_MASTERS, MasterSpec
from .plan import RenderPlan, RenderPlanError, ir_to_filtergraph
from .queue import RenderQueue
from .repo import InMemoryRenderRepo, PgRenderRepo, RenderRecord, RenderRepo, render_key
from .runner import FakeFfmpegRunner, FfmpegRunner, RenderError, SubprocessFfmpegRunner
from .service import RenderService
from .subtitles import build_ass

__all__ = [
    "PLATFORM_MASTERS", "MasterSpec",
    "RenderPlan", "RenderPlanError", "ir_to_filtergraph",
    "RenderQueue",
    "InMemoryRenderRepo", "PgRenderRepo", "RenderRecord", "RenderRepo", "render_key",
    "FakeFfmpegRunner", "FfmpegRunner", "RenderError", "SubprocessFfmpegRunner",
    "RenderService",
    "build_ass",
]
