# CLAUDE.md — VIOS (Video Intelligence OS)

Contexto que Claude Code lee al abrir este repo. Léelo entero antes de tocar nada.

## Qué es VIOS

Motor de **edición** de vídeo por IA para Cliender. Toma material **bruto** (grabado
por un humano) + una ficha de cliente + un playbook y produce piezas optimizadas por
plataforma (reel 9:16, etc.). **VIOS solo EDITA, nunca crea contenido**: no genera
b-roll IA ni inventa material; solo usa el bruto y la biblioteca real del cliente.

## Regla de oro (operativa)

- **El código vive en git, NO en OneDrive.** Nunca clones ni edites este repo dentro
  de una carpeta sincronizada (OneDrive/Drive/Dropbox): bind-mount de Docker sobre
  OneDrive corrompe overlay2 (`EDEADLK`). Clona en `~/dev/vios` o similar.
- **Secretos nunca a git.** `.env` está en `.gitignore`. Solo `.env.example` (placeholders).
- **LLM por suscripción, no API.** Los agentes usan `provider="subscription"`
  (Claude Agent SDK sobre el login de Claude Code). `provider="api"` (key facturada)
  solo para escala. Ver `apps/engine/src/vios_engine/agents/llm.py`.

## Setup de una máquina nueva

Requisitos: **Docker Desktop**, **uv** (Python 3.12), **git**, y opcional **Node 20**
para `render-svc`. Instalar uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

```bash
git clone https://github.com/nicogemini1998-commits/vios.git ~/dev/vios
cd ~/dev/vios
cp .env.example .env          # rellenar SUPABASE_* cuando exista el proyecto
make up                       # docker compose up (db + engine + render-svc)
make test                     # suite completa
make health                   # curl al /health del engine
```

## Comandos

- Tests engine: `cd apps/engine && uv run --with pytest --with pytest-asyncio pytest tests/ -q`
- Tests contracts: `cd packages/contracts && uv run --with pytest pytest tests/ -q`
- Lint: `uvx ruff check apps/engine/src packages/contracts/src` (`--fix` para autofix)
- Export JSON Schema de la IR: `python packages/contracts/scripts/export_schema.py`

## Arquitectura (monorepo)

- `packages/contracts/` — contratos Pydantic compartidos (**fuente de verdad**):
  `TimelineIR` (central), `ClientProfile` (ficha A–H), `Playbook`, `MediaIntelligence`,
  `EditPlan`. Ops: validate/diff/to_json/from_json + JSON Schema versionado.
- `apps/engine/` — FastAPI + CLI `vios` + pipeline + agentes:
  - `pipeline/` — grafo de fases (Kahn), JobState, retries, TokenBudget/job, checkpoints IR.
  - `agents/` — Director+Story (LLM) → EditPlan; Edit (determinista) → Timeline IR.
  - `media/` — ingest→storage→proxy→hash cache. `intelligence/` — Whisper/PySceneDetect/librosa.
- `apps/render-svc/` — Node/Remotion (placeholder hasta F5), host :4011.
- `db/migrations/` — SQL idempotente. `playbooks/` — playbooks + fichas cliente (YAML).
- `docs/adr/` — decisiones D1–D9.

## Convenciones de código (respétalas)

- **Unidades:** MediaIntelligence y EditPlan en **segundos**; Timeline IR en **frames**
  (`fps` en la raíz). Conversión segundos↔frames: UNA sola función canónica en
  `timeline_ops` (`s_to_frames`/`frames_to_s`); ningún agente hace aritmética de fps
  inline. El Edit Agent sigue siendo el único que MATERIALIZA cortes/clips desde el
  EditPlan; las capas F4 solo posicionan sobre la IR ya cortada usando esas funciones
  y el helper de remapeo `source_frame_to_timeline`.
- **Timeline IR inmutable por revisión:** nunca mutar una IR; usar `TimelineDraft` →
  `.commit(by, why)` que produce revisión+1 con `Decision` auditada (quién y por qué).
- **Anti-alucinación:** los agentes solo usan datos reales (transcript, biblioteca).
  Ante duda → marcar y preguntar, nunca inventar. Subtítulos = transcript literal.
- **Testeable sin ML/API:** todo por interfaces inyectables; los tests usan `FakeLLM`
  y fakes de ffmpeg/whisper. Ningún test llama a un modelo real.
- **Estilo:** ruff limpio, funciones pequeñas, español en docstrings/comentarios.

## Protocolo por módulo (obligatorio)

1. Doc de diseño (11 puntos) antes del código → validar con Nico.
2. TDD: tests del contrato primero.
3. Cierre: tests verdes + ruff limpio + doc del módulo + entrada en BITACORA + commit.
4. Si detectas una mala decisión del plan → STOP, propón alternativa, no codifiques aún.

## Estado y próximo paso

- **Completadas:** F0 Fundación (M0) · F1 Contratos (M1–M2) · F2 Ingesta (M3–M4) ·
  F3 Cerebro (M5–M7) · **F4 COMPLETA** (M8 Subtitle+Branding · M9 Visual/Motion+Audio ·
  M10 B-Roll+CTA/Thumbnail). 11/14 módulos. Suite verde (engine 106, contracts 50).
- **Próximo: M11 Render Service** (arranca F5): IR → Remotion composition →
  preview 480p → masters por plataforma (generalizar el servicio CDPro :4010,
  host :4011 en `apps/render-svc/`). Dependencia externa Remotion: si falta una
  pieza, stub + test + nota en BITACORA y seguir.
  Grafo actual (10 fases): ingest → director → story → edit → subtitle →
  branding → visual → audio → broll → cta.
- **Plan maestro y docs de módulos** viven en OneDrive (carpeta VIOS de Cliender), no
  en el repo. Pídeselos a Nico si necesitas el detalle de diseño.
