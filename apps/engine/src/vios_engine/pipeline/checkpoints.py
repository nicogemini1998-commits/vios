"""Checkpoints IR por revisión (M5). Cada fase que produce IR persiste snapshot.

Historial completo en tabla `timelines` (D1: rollback trivial). En tests se usa
el store en memoria; el contrato es el mismo.
"""
from __future__ import annotations

from typing import Protocol

from vios_contracts import TimelineIR, to_json


class CheckpointStore(Protocol):
    async def save(self, job_id: str, phase: str, ir: TimelineIR) -> None: ...
    async def latest(self, project_id: str) -> TimelineIR | None: ...


class InMemoryCheckpointStore:
    """Store para tests y ejecución local sin PG."""

    def __init__(self) -> None:
        self.saved: list[tuple[str, str, TimelineIR]] = []

    async def save(self, job_id: str, phase: str, ir: TimelineIR) -> None:
        self.saved.append((job_id, phase, ir))

    async def latest(self, project_id: str) -> TimelineIR | None:
        for _, _, ir in reversed(self.saved):
            if ir.project_id == project_id:
                return ir
        return None


class PGCheckpointStore:
    """Persiste revisiones IR en `timelines` (asyncpg pool)."""

    def __init__(self, pool) -> None:
        self._pool = pool

    async def save(self, job_id: str, phase: str, ir: TimelineIR) -> None:
        await self._pool.execute(
            """
            INSERT INTO timelines (project_id, revision, ir)
            VALUES ($1, $2, $3::jsonb)
            """,
            ir.project_id, ir.revision, to_json(ir),
        )

    async def latest(self, project_id: str) -> TimelineIR | None:
        from vios_contracts import from_json

        row = await self._pool.fetchrow(
            """
            SELECT ir FROM timelines
            WHERE project_id = $1 AND ir IS NOT NULL
            ORDER BY revision DESC LIMIT 1
            """,
            project_id,
        )
        return from_json(row["ir"]) if row else None
