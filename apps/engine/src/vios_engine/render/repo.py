"""Registro de renders — tabla propia `renders` (decisión Nico M11 §6, no jsonb).

La clave (project_id, timeline_revision, quality, platform) es también la base
de la idempotencia: un render `done` para esa tupla no se repite.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol


def render_key(project_id: str, revision: int, quality: str, platform: str) -> str:
    return f"{project_id}-r{revision}-{quality}-{platform}"


@dataclass
class RenderRecord:
    id: str
    project_id: str
    timeline_revision: int
    quality: str                    # preview | master
    platform: str
    status: str = "queued"          # queued | rendering | done | error
    url: str = ""
    error: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class RenderRepo(Protocol):
    async def find(self, project_id: str, revision: int,
                   quality: str, platform: str) -> RenderRecord | None: ...
    async def save(self, record: RenderRecord) -> None: ...


class InMemoryRenderRepo:
    """Repo para tests y ejecución local sin PG."""

    def __init__(self) -> None:
        self.records: dict[str, RenderRecord] = {}

    async def find(self, project_id: str, revision: int,
                   quality: str, platform: str) -> RenderRecord | None:
        return self.records.get(render_key(project_id, revision, quality, platform))

    async def save(self, record: RenderRecord) -> None:
        self.records[record.id] = record


class PgRenderRepo:
    """Persiste en `renders` (asyncpg pool). Upsert por id (clave de idempotencia)."""

    def __init__(self, pool) -> None:
        self._pool = pool

    async def find(self, project_id: str, revision: int,
                   quality: str, platform: str) -> RenderRecord | None:
        row = await self._pool.fetchrow(
            """
            SELECT id, project_id, timeline_revision, quality, platform,
                   status, url, error, created_at
            FROM renders
            WHERE project_id = $1 AND timeline_revision = $2
              AND quality = $3 AND platform = $4
            """,
            project_id, revision, quality, platform,
        )
        return RenderRecord(**dict(row)) if row else None

    async def save(self, record: RenderRecord) -> None:
        await self._pool.execute(
            """
            INSERT INTO renders (id, project_id, timeline_revision, quality,
                                 platform, status, url, error, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (id) DO UPDATE
              SET status = EXCLUDED.status, url = EXCLUDED.url,
                  error = EXCLUDED.error
            """,
            record.id, record.project_id, record.timeline_revision,
            record.quality, record.platform, record.status,
            record.url, record.error, record.created_at,
        )
