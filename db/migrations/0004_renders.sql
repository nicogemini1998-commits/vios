-- M11: tabla propia de renders (decisión Nico — trazable e indexable, no jsonb en jobs)
CREATE TABLE IF NOT EXISTS renders (
    id                TEXT PRIMARY KEY,
    project_id        TEXT NOT NULL,
    timeline_revision INTEGER NOT NULL,
    quality           TEXT NOT NULL CHECK (quality IN ('preview', 'master')),
    platform          TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued', 'rendering', 'done', 'error')),
    url               TEXT NOT NULL DEFAULT '',
    error             TEXT NOT NULL DEFAULT '',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- clave de idempotencia: un render por (proyecto, revisión, calidad, plataforma)
CREATE UNIQUE INDEX IF NOT EXISTS idx_renders_key
    ON renders (project_id, timeline_revision, quality, platform);
