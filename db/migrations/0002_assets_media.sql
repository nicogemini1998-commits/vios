-- M3: extiende assets con proxy/metadata/estado. Idempotente (PG16 ADD COLUMN IF NOT EXISTS).
ALTER TABLE assets ADD COLUMN IF NOT EXISTS proxy_url    text;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS audio_url    text;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS mime         text;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS size_bytes   bigint;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS width        int;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS height       int;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS duration_s   double precision;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS fps          double precision;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS has_audio    boolean;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS status       text DEFAULT 'ready';
ALTER TABLE assets ADD COLUMN IF NOT EXISTS error        text;
CREATE INDEX IF NOT EXISTS idx_assets_hash ON assets(hash);
