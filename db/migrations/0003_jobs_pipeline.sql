-- M5: extiende jobs con estado de pipeline, budget y trazabilidad. Idempotente.
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS phase          text;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS error          text;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS tokens_budget  int;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS tokens_spent   int DEFAULT 0;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS payload        jsonb;   -- brief, playbook_id, platform, phases
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS updated_at     timestamptz NOT NULL DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_timelines_project_rev ON timelines(project_id, revision);
