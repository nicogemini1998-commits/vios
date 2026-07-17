# M5–M7 · F3 Cerebro — Pipeline Engine + Director/Story + Edit Agent (v1)

> VIOS · 2026-07-16 · KAREN (Fable 5) · Commit `fcf0b96` · Estado: CERRADO

## 1. Objetivo
Primer "bruto → timeline coherente": motor de pipeline determinista (M5) que orquesta los primeros agentes LLM (M6 Director+Story → EditPlan) y el Edit Agent determinista (M7 EditPlan → Timeline IR v1).

## 2. Requisitos funcionales
- **M5**: grafo de fases explícito (D2) con orden topológico; estado job/fase; retries por fase (max_attempts); presupuesto tokens por job (aborta al superarlo, sin retry); checkpoint IR por revisión en cada fase que produce timeline.
- **M6**: `DirectorAgent` (brief+ClientProfile+Playbook+MediaIntelligence → intent/arc/target_duration/beats en segundos) y `StoryAgent` (plan+transcript → momentos con `why` + hook candidates). JSON estricto; 1 reintento con el error en el prompt.
- **M7**: `EditAgent` convierte EditPlan (segundos) a IR (frames): clips consecutivos video+audio, markers beat/hook/cta, Decision auditada vía `TimelineDraft.commit`.

## 3. No funcionales
Cero LLM en tests (FakeLLM scriptado); coste acotado (TokenBudget + BudgetExceededError no reintentable); todo momento auditable (`why` obligatorio); anti-alucinación (Story solo usa rangos del transcript; hook literal).

## 4. Diseño
- `vios_engine/pipeline/`: `graph.py` (PhaseSpec/PipelineGraph/Kahn determinista + `vios_default_graph` ingest→director→story→edit), `models.py` (JobState/PhaseState), `budget.py`, `checkpoints.py` (Protocol + InMemory + PGCheckpointStore→tabla `timelines`), `engine.py` (PipelineEngine.run: retries, charge budget, checkpoint, fail con causa).
- `vios_engine/agents/`: `llm.py` (LLMClient Protocol, AnthropicLLM lazy-import, FakeLLM, `extract_json`), `director.py`, `story.py`, `edit.py`.
- Eval-first: `validate_edit_plan` (en contracts) es el harness — duración vs playbook, beats≈target (±15%), momentos contiguos/en rango/≈target (±25%), asset real, hook ≤max_seconds. El agente que no pasa el eval reintenta 1 vez con feedback y si no, falla explícito.

## 5. Interfaces
`PhaseHandler = async (PipelineContext) -> PhaseResult{output, ir?, tokens_used}` · `LLMClient.complete(system, prompt, max_tokens) -> LLMResult{text, tokens_in/out}` · `DirectorAgent.plan(...)->EditPlan` · `StoryAgent.select_moments(...)->EditPlan` · `EditAgent.build_timeline(plan, playbook)->TimelineIR`.

## 6. Modelos de datos
Contrato nuevo `vios_contracts.edit_plan`: `EditPlan{project/client/playbook/platform, intent, arc, target_duration_s, structure[PlannedBeat], moments[SelectedMoment{order,asset,start_s,end_s,beat,why}], hooks[HookCandidate{score,text}]}`. Migración `0003_jobs_pipeline.sql`: jobs + phase/error/tokens_budget/tokens_spent/payload/updated_at + índices.

## 7. Casos límite
JSON con fence/prosa (extract_json); JSON inválido 2 veces → LLMParseError; momento fuera del asset → eval rechaza; budget agotado a mitad → job failed sin retry ni fases posteriores; EditPlan sin momentos → EditAgent rechaza; ciclo/dep desconocida en grafo → PipelineGraphError.

## 8. Riesgos
Coste LLM (mitigado: budget hard + eval antes de avanzar); calidad plan (mitigado: validadores semánticos, no vibes); grafo fijo puede quedarse corto en F4 (paralelo sobre IR) → PipelineGraph ya soporta deps arbitrarias.

## 9. Tests
Contracts: 12 nuevos EditPlan (33 total verdes). Engine: 21 nuevos (55 verdes + 3 skip ML): grafo (orden/ciclo/dup/dep), budget, motor (happy/retry/fail/budget-abort/checkpoint), Director (ok/retry-feedback/fail/duración fuera), Story (ok/momento fuera de asset), EditAgent (frames exactos, markers, decisión), **golden brief e2e** (pipeline completo FakeLLM → IR válida dentro del rango del playbook, checkpoint persistido).

## 10. Plan implementación
Hecho en esta sesión: contrato+eval → tests → pipeline → agentes → migración → suite verde → ruff limpio → commit `fcf0b96`.

## 11. Docs/pendientes
- **M5.1/M6.1 (al crear Supabase + API key):** wiring real en FastAPI/CLI (crear job → correr pipeline con AnthropicLLM + PGCheckpointStore), persistir JobState en `jobs`, medir coste real por vídeo (fijar X€ del plan §8).
- Golden briefs con salidas esperadas contra LLM real (suite eval separada, no CI).
- Config nueva: `ANTHROPIC_API_KEY` (vacía = agentes off), `JOB_TOKEN_BUDGET` (default 200k).
