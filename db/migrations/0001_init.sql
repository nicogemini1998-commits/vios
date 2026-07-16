-- VIOS schema inicial (M0). Núcleo, ampliable. Idempotente (CL4).
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS projects (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id  text NOT NULL,
    brief      text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS assets (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  uuid REFERENCES projects(id) ON DELETE CASCADE,
    storage_url text NOT NULL,          -- media SIEMPRE por URL, nunca base64 (lección CDPro)
    hash        text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jobs (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  uuid REFERENCES projects(id) ON DELETE CASCADE,
    status      text NOT NULL DEFAULT 'pending',
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS timelines (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  uuid REFERENCES projects(id) ON DELETE CASCADE,
    revision    int  NOT NULL DEFAULT 0,       -- historial completo (D1: rollback trivial)
    ir          jsonb,                          -- hueco reservado Timeline IR (M1)
    created_at  timestamptz NOT NULL DEFAULT now()
);
