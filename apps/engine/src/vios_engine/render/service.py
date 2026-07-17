"""RenderService — orquesta idempotencia → cola → plan → ffmpeg → registro.

El render es CONSUMIDOR de la IR, nunca editor: no produce revisiones nuevas.
Preview 480p barata; master solo se dispara explícitamente tras aprobación
humana (manual §2, 2 puertas) — este servicio no impone la puerta, el flujo sí.
"""
from __future__ import annotations

from pathlib import Path

from vios_contracts import TimelineIR

from .plan import ASS_PLACEHOLDER, RenderPlanError, ir_to_filtergraph
from .queue import RenderQueue
from .repo import RenderRecord, RenderRepo, render_key
from .runner import FfmpegRunner, RenderError


class RenderService:
    def __init__(
        self,
        repo: RenderRepo,
        runner: FfmpegRunner,
        queue: RenderQueue,
        output_dir: Path,
        timeout_s: float = 600.0,
    ) -> None:
        self._repo = repo
        self._runner = runner
        self._queue = queue
        self._output_dir = Path(output_dir)
        self._timeout_s = timeout_s

    async def render(
        self,
        ir: TimelineIR,
        quality: str,
        platform: str,
        client_id: str,
        asset_paths: dict[str, str],
        font_files: dict[str, str] | None = None,
    ) -> RenderRecord:
        existing = await self._repo.find(ir.project_id, ir.revision, quality, platform)
        if existing is not None and existing.status == "done":
            return existing                    # idempotencia: URL cacheada

        record = RenderRecord(
            id=render_key(ir.project_id, ir.revision, quality, platform),
            project_id=ir.project_id,
            timeline_revision=ir.revision,
            quality=quality,
            platform=platform,
            status="queued",
        )
        await self._repo.save(record)

        async with self._queue.slot(client_id):
            record.status = "rendering"
            await self._repo.save(record)
            try:
                plan = ir_to_filtergraph(ir, asset_paths, quality, platform, font_files)
                out_path = self._output_dir / f"{record.id}.mp4"
                await self._runner.run(self._build_args(plan, record.id, out_path),
                                       self._timeout_s)
                record.status = "done"
                record.url = str(out_path)
            except (RenderPlanError, RenderError) as exc:
                record.status = "error"
                record.error = str(exc)
        await self._repo.save(record)
        return record

    async def thumbnail(self, asset_path: str, frame: int, fps: int,
                        out_path: Path) -> Path:
        """Extrae el frame candidato del SOURCE (marker thumbnail de M10)."""
        at = f"{frame / fps:.6f}"
        await self._runner.run(
            ["-ss", at, "-i", asset_path, "-frames:v", "1", "-q:v", "2",
             str(out_path)],
            self._timeout_s,
        )
        return out_path

    def _build_args(self, plan, record_id: str, out_path: Path) -> list[str]:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        filter_complex = plan.filter_complex
        if plan.ass_content is not None:
            ass_path = self._output_dir / f"{record_id}.ass"
            ass_path.write_text(plan.ass_content, encoding="utf-8")
            filter_complex = filter_complex.replace(ASS_PLACEHOLDER, str(ass_path))
        args: list[str] = []
        for tokens in plan.inputs:
            args.extend(tokens)
        args += ["-filter_complex", filter_complex, *plan.output_args, str(out_path)]
        return args
