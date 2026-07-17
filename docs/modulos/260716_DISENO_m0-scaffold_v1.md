# DISEÑO M0 — Repo + Esqueleto (F0 Fundación)

> **Módulo:** M0 · **Fase:** F0 · **Versión:** v1 · **Fecha:** 2026-07-16
> **Autor:** KAREN (Opus 4.8) · **Plan padre:** `260716_PLAN_video-intel-os_v1.md`
> **Estado:** DISEÑO — pendiente validación Nico antes de código
> **Decisión Supabase confirmada:** proyecto **nuevo dedicado VIOS** (coherente con D9 standalone)

---

## 1. Objetivo

Levantar el esqueleto ejecutable del monorepo VIOS: estructura de carpetas, contratos vacíos, servicios arrancables con `docker compose up`, CI local mínimo y schema Supabase inicial. **No hay lógica de negocio en M0** — es la fundación sobre la que se construyen M1–M14. Al cerrar M0, cualquier agente/dev clona el repo, arranca, y todos los healthchecks responden verde.

Segundo objetivo: **confirmar o corregir las decisiones D1–D9** del plan mediante ADRs escritos, antes de invertir en contratos (F1).

---

## 2. Requisitos funcionales

- **RF1** — `git clone` + `docker compose up` levanta: `engine` (FastAPI), `render-svc` (Node/Remotion placeholder), `db` (Postgres) y opcionalmente el bridge a Supabase cloud.
- **RF2** — `GET /health` en `engine` devuelve `{status, version, deps: {db, storage}}` con chequeo real de conexión a Postgres.
- **RF3** — `render-svc` expone `GET /health` (placeholder, sin render aún).
- **RF4** — `packages/contracts/` existe con módulos vacíos tipados para IR, ClientProfile, Playbook, MediaIntelligence (solo stubs + `version` field), importables desde `engine`.
- **RF5** — `playbooks/` con 1 archivo YAML de ejemplo mínimo validado por el loader stub.
- **RF6** — CLI mínima (`vios --version`, `vios health`) que golpea el engine.
- **RF7** — Schema Supabase inicial aplicable vía migración: tablas `projects`, `assets`, `jobs`, `timelines` (solo columnas núcleo + `created_at`), sin FKs complejas todavía.
- **RF8** — `.env.example` versionado; `.env` real fuera de OneDrive y gitignored.

## 3. Requisitos no funcionales

- **RNF1 · Ubicación** — código en `~/dev/vios/` (git). **NUNCA en OneDrive** (bind-mount Docker → EDEADLK). OneDrive solo docs.
- **RNF2 · Reproducibilidad** — versiones pinneadas: Python 3.12, Node 20 LTS, imágenes Docker con tag fijo (no `latest`).
- **RNF3 · Arranque** — `docker compose up` en frío < 90 s tras build; healthchecks verdes < 30 s.
- **RNF4 · Coste cero LLM** — M0 no invoca modelos. Puro andamiaje.
- **RNF5 · Secretos** — jamás en repo. `.env` local + Supabase keys en `.env`; validación de presencia al arrancar (fail-fast).
- **RNF6 · Lint/format** — ruff + black (Python), prettier (Node). Pre-commit opcional.

## 4. Diseño

### 4.1 Estructura del monorepo
```
~/dev/vios/
├── apps/
│   ├── engine/                 # FastAPI · Python 3.12
│   │   ├── src/vios_engine/
│   │   │   ├── main.py         # app + /health
│   │   │   ├── config.py       # carga .env, fail-fast
│   │   │   ├── db.py           # pool Postgres (asyncpg)
│   │   │   └── cli.py          # entrypoint `vios`
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   └── render-svc/             # Node 20 · Remotion (placeholder)
│       ├── src/index.ts        # server + /health
│       ├── package.json
│       └── Dockerfile
├── packages/
│   └── contracts/              # schemas compartidos (stubs en M0)
│       ├── timeline_ir.py
│       ├── client_profile.py
│       ├── playbook.py
│       └── media_intelligence.py
├── playbooks/
│   └── reel-educativo.example.yaml
├── db/
│   └── migrations/
│       └── 0001_init.sql
├── docker-compose.yml
├── .env.example
├── .gitignore
├── ruff.toml
└── README.md
```

### 4.2 Servicios Docker Compose
| Servicio | Imagen base | Puerto | Rol M0 |
|---|---|---|---|
| `engine` | python:3.12-slim | 8000 | FastAPI + /health + CLI |
| `render-svc` | node:20-slim | 4010 | placeholder /health (base futura para Remotion CDPro) |
| `db` | postgres:16 | 5432 | PG local para dev/tests; Supabase cloud vía `.env` en real |

Nota: en dev usamos `db` local; producción apunta a **Supabase nuevo VIOS** por `DATABASE_URL`. Mismo código, distinto endpoint.

### 4.3 Config y fail-fast
`config.py` lee `.env` con pydantic-settings. Variables requeridas: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `STORAGE_BUCKET`. Si falta alguna → excepción al import, el contenedor no arranca (evita el clásico "arrancó pero medio roto").

### 4.4 ADRs (entregable paralelo)
Un ADR por decisión D1–D9 en `docs/adr/` del repo (espejo resumido en `01. MODULOS/`). Formato: contexto, decisión, consecuencias, estado (aceptada/revisada). M0 es el momento de impugnarlas barato.

---

## 5. Interfaces

- **HTTP engine:** `GET /health`, `GET /version`.
- **HTTP render-svc:** `GET /health`.
- **CLI:** `vios --version`, `vios health` (imprime estado de engine + db).
- **Import Python:** `from vios_contracts import TimelineIR, ClientProfile, Playbook, MediaIntelligence` (stubs con `version`).
- **DB:** migración SQL idempotente aplicable con `psql` o script `make migrate`.

Sin MCP en M0 (llega en M13). Sin endpoints de negocio.

---

## 6. Modelos de datos (solo stubs núcleo)

Contratos = clases Pydantic v2 con `schema_version: str` y campos mínimos; el detalle real llega en M1/M2. Objetivo M0: que existan, importen y validen un objeto vacío/ejemplo.

Tablas SQL `0001_init.sql` (núcleo, ampliables):
- `projects(id uuid pk, client_id text, brief text, created_at)`
- `assets(id uuid pk, project_id fk, storage_url text, hash text, created_at)`
- `jobs(id uuid pk, project_id fk, status text, created_at)`
- `timelines(id uuid pk, project_id fk, revision int, ir jsonb, created_at)`

`ir jsonb` reserva el hueco de la Timeline IR (D1) sin comprometer schema aún.

---

## 7. Casos límite

- **CL1** — `.env` ausente o incompleto → fail-fast claro, no arranque silencioso a medias.
- **CL2** — Puerto ocupado (8000/4010/5432) → documentar override por `.env`; compose usa variables de puerto.
- **CL3** — Alguien clona dentro de OneDrive → README avisa explícito + check opcional en `make setup` que aborta si el path contiene `OneDrive`.
- **CL4** — Migración corrida dos veces → SQL idempotente (`create table if not exists`).
- **CL5** — Máquina sin GPU (relevante desde F2, se documenta ya) → M0 no afecta, pero README lista requisitos futuros.

---

## 8. Riesgos

| Riesgo | Prob. | Mitigación |
|---|---|---|
| Sobre-ingeniería del esqueleto (YAGNI) | Media | M0 = stubs, no lógica. Prohibido implementar contratos reales aquí |
| Divergencia dev-local vs Supabase | Media | Mismo `DATABASE_URL` abstrae; probar ambos en M0 antes de cerrar |
| Deriva de versiones (`latest`) | Baja | Tags pinneados obligatorios (RNF2) |
| Repo acaba en OneDrive por costumbre | Media | CL3 + aviso en README + memoria persistente |

---

## 9. Tests

- **T1** — `pytest`: `/health` responde 200 con `db: ok` (con PG de test vía compose o testcontainer).
- **T2** — `config.py` lanza excepción si falta variable requerida (parametrizado).
- **T3** — Import de los 4 contratos stub + instanciación de objeto ejemplo válido.
- **T4** — Loader de playbook lee `reel-educativo.example.yaml` sin error.
- **T5** — CLI `vios health` retorna exit 0 con engine arriba, ≠0 con engine caído.
- **T6 (smoke)** — script CI: `docker compose up -d` → poll `/health` engine + render-svc → `down`. Verde = M0 cerrado.

Cobertura objetivo M0: los stubs no exigen 80% (poca lógica); sí exigir que T1–T6 pasen en CI local.

---

## 10. Plan de implementación (orden)

1. `git init` en `~/dev/vios/` + `.gitignore` + README con aviso OneDrive.
2. `packages/contracts/` con 4 stubs Pydantic (`schema_version`).
3. `apps/engine/`: pyproject, `config.py` (fail-fast), `db.py` (asyncpg pool), `main.py` (/health, /version), `cli.py`.
4. `db/migrations/0001_init.sql` + `make migrate`.
5. `apps/render-svc/`: server Node mínimo con /health + Dockerfile.
6. `docker-compose.yml` (engine + render-svc + db + healthchecks) + `.env.example`.
7. `playbooks/reel-educativo.example.yaml` + loader stub + test T4.
8. Tests T1–T5 + script smoke T6.
9. ADRs D1–D9 en `docs/adr/`.
10. `docker compose up` en frío → todo verde → cierre.

---

## 11. Documentación / cierre

- Este doc en `01. MODULOS/`.
- `README.md` del repo (arranque, requisitos, aviso OneDrive).
- 9 ADRs (D1–D9), espejo resumido en `01. MODULOS/`.
- Entrada en `BITACORA.md`: "M0 cerrado — repo arrancable, healthchecks verdes, ADRs D1–D9 fijadas".
- Memoria persistente: actualizar `project_vios_plan.md` con estado F0 completado + ruta repo.

---

## Salida esperada F0 (criterio de cierre)

✅ `docker compose up` levanta engine + render-svc + db · ✅ healthchecks verdes · ✅ tests T1–T6 pasan en CI local · ✅ 4 contratos stub importables · ✅ migración inicial aplicada · ✅ ADRs D1–D9 escritas y confirmadas/corregidas por Nico.

---

*Próximo paso: Nico valida este diseño M0 (especialmente estructura monorepo, tablas núcleo y decisión Supabase nuevo). Tras OK → implementación M0 según §10. Luego M1 (Timeline IR) — el módulo más crítico del proyecto.*
