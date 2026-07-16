# VIOS — Video Intelligence OS

Sistema operativo de **edición** de contenido: bruto entregado por humano → piezas
optimizadas por plataforma. VIOS **solo edita, nunca crea** material audiovisual nuevo.

Plan maestro y docs: OneDrive `06. RECURSOS CLIENDER/.../05. Video Intel OS/`.
Este repo es SOLO código.

## ⚠️ Regla crítica

**Este repo NO puede vivir en OneDrive.** Bind-mounts de Docker sobre OneDrive
provocan `EDEADLK` y corrupción. Clónalo en `~/dev/vios/` o similar. `make setup`
aborta si detecta `OneDrive` en la ruta.

## Requisitos

- Docker + Docker Compose
- (dev local sin docker) uv, Python 3.12, Node 20+

## Arranque

```bash
cp .env.example .env      # rellena SUPABASE_* para produccion
make up                   # docker compose up con healthchecks
make health               # vios health contra el engine
make test                 # pytest + smoke
```

## Estructura

| Ruta | Qué |
|---|---|
| `apps/engine/` | FastAPI + CLI + pipeline (Python 3.12) |
| `apps/render-svc/` | Remotion + FFmpeg (Node) — placeholder en M0 |
| `packages/contracts/` | Schemas compartidos: Timeline IR, ClientProfile, Playbook, MediaIntelligence |
| `playbooks/` | YAML de playbooks (datos, no código) |
| `db/migrations/` | SQL idempotente |
| `docs/adr/` | Decisiones de arquitectura D1–D9 |

Estado: **M0 (F0 Fundación)** — esqueleto arrancable, sin lógica de negocio.
