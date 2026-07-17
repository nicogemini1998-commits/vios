# M12 · F5 Render + QA — QA/Compliance Agent + loop de corrección acotado (v1)

> VIOS · 2026-07-17 · KAREN (Fable 5) · Estado: **BORRADOR — pendiente validación de Nico ANTES de codear** (directiva F5+)
> Último módulo antes del **HITO MVP** (bruto real → reel publicable, validar con Toni). M12 es el guardián automático de las reglas del manual §2 sobre la IR final, ANTES de gastar ffmpeg y ANTES de la puerta humana.

## 1. Objetivo
**QAAgent determinista** que audita la IR final (rev 7) contra el manual §2, la ficha del cliente y el playbook, y produce un **QAReport** con findings tipados (`block`/`warn`), cada uno con regla violada, evidencia y **agente responsable**. Con findings corregibles, un **loop de corrección acotado (máx 2 pasadas, plan §5)** re-ejecuta la cadena F4 desde el checkpoint del agente responsable con constraints derivados de los findings (p.ej. "sin CTA", "sin ese asset"). `block` no corregible → job failed con el informe completo (equivalente a NEEDS_INPUT: el humano decide). El QA nunca "arregla" inventando: solo QUITA lo que no es trazable/aprobado, jamás añade.

## 2. Requisitos funcionales
**Checks v1 (todos deterministas, cero LLM) — cada uno mapea a una regla del manual §2:**

| # | Check | Regla §2 | Severidad | Responsable |
|---|---|---|---|---|
| Q1 | Trazabilidad de sources: todo clip video/audio/graphic-imagen apunta a un asset del brief (intel) o de la biblioteca/ficha | 1 | block | quien lo insertó (por Decision) |
| Q2 | Subtítulos literales: el texto de cada clip subtitle existe VERBATIM en el transcript del source correspondiente | 3 | block | subtitle |
| Q3 | Texto en pantalla aprobado: CTA == `audience.cta.text` de la ficha o `default_text` del playbook, carácter a carácter | 4 | block | cta |
| Q4 | Blacklist (C.voice): palabras/temas/competidores/claims prohibidos en subtítulos y CTA (case/acentos-insensitive) | 5 | block | subtitle/cta |
| Q5 | Reglas Cliender heredadas: "GHL"/"Go High Level"/"GoHighLevel" en cualquier texto; patrones de precio (€, EUR, \d+ ?euros) en textos de cliente | 7 | block | subtitle/cta |
| Q6 | Duración total dentro de `ideal_duration[platform]` del playbook | — | block | edit |
| Q7 | Hook: marker `hook` presente y ≤ `hook.max_seconds`; pieza arranca en frame 0 sin hueco | — | warn | edit |
| Q8 | Branding: `intro_outro.mandatory` → outro presente; logo de la ficha → track graphic con `logo_overlay` | 1 | block/warn | branding |
| Q9 | Auditoría completa: `validate(ir)` + toda revisión tiene Decision con `why` no vacío + markers `cta`/`thumbnail` presentes si sus policies aplican | 6 | warn | pipeline |
| Q10 | `never_do` de la ficha (E): matching literal contra textos en pantalla | 5 | block | cta/subtitle |

- **QAReport**: `{verdict: pass|fail, findings: [{check, rule, severity, evidence, responsible, fix: DROP_CTA|DROP_BROLL_ASSET|DROP_MUSIC|DROP_SUBTITLE_CLIP|None}]}`. `fix=None` = no corregible automáticamente.
- **Loop de corrección (máx 2)**: si TODOS los `block` tienen `fix`, se reconstruye la cadena F4 desde el checkpoint previo al primer agente responsable, pasando `QAConstraints` (assets/textos vetados) a los agentes re-ejecutados; se re-audita. 2ª pasada aún con `block` → failed con informe. Los agentes F4 ganan un parámetro opcional `constraints` (default None = comportamiento actual intacto).
- **Pipeline**: fase `qa` entre `cta` y `render` (grafo = 12 fases) — no se quema ffmpeg en una IR que no pasa QA. QA aprobada = 1 revisión con Decision `qa: pass (N warns)` (rev 8, auditable como todo lo demás); el render pasa a renderizar rev 8.

## 3. No funcionales
Determinista y reproducible (mismos inputs → mismo veredicto; cero LLM en v1 — el matching semántico de claims llega post-MVP si hace falta); el QA solo QUITA, nunca añade (anti-alucinación); findings con evidencia exacta (texto, clip id, frame) — nada de "parece que"; testeable en memoria; el loop jamás re-llama al LLM (Director/Story ya validados por su eval M6: el loop solo re-ejecuta capas F4 deterministas, así que converge por construcción — cada pasada elimina elementos, no los cambia).

## 4. Diseño
- `vios_engine/agents/qa.py`: `QAAgent.review(ir, intel_by_asset, playbook, profile) -> QAReport` + `apply_verdict(ir, report) -> TimelineIR` (commit de la revisión QA).
- `QAConstraints` (dataclass simple en engine, no contrato): `banned_assets: set[str]`, `drop_cta: bool`, `drop_music: bool`, `banned_subtitle_clips: set[str]`. Los agentes F4 lo respetan con 2-3 líneas cada uno (si el asset está vetado → skip anotado "vetado por QA pasada N").
- Orquestación del loop en el handler de fase (el PipelineEngine NO se toca — sigue lineal): el handler `qa` guarda los checkpoints previos en `ctx.outputs`, re-ejecuta la sub-cadena en memoria y audita de nuevo. Máx 2 pasadas, constante `QA_MAX_LOOPS = 2` (plan §5: "max 2 loops").
- Normalización de texto para Q4/Q5/Q10: lowercase + sin acentos (NFD) + colapso de espacios — una sola función compartida.
- Q2 (literalidad): el texto del clip subtitle debe ser subcadena de la concatenación normalizada de los segments del transcript del asset del clip de vídeo que suena en su ventana; los `[inaudible]` pasan (regla 3: marcados, no inventados).

## 5. Interfaces
`QAAgent.review(ir, intel_by_asset, playbook, profile) -> QAReport` · `QAAgent.apply_verdict(ir, report) -> TimelineIR` · fase `qa` como `PhaseHandler` (produce IR rev 8 si pass; lanza con informe si fail definitivo) · agentes F4 con parámetro opcional `constraints`.

## 6. Modelos de datos
**Sin cambios en `vios_contracts`** (QAReport/QAConstraints viven en engine — el informe NO es un contrato compartido hasta que el MCP F6 lo exponga; entonces se promociona). Config: `QA_MAX_LOOPS` como constante (no env: es una regla del plan, no un tunable de despliegue).

## 7. Casos límite
Ficha sin blacklist → Q4 pasa con warn "ficha sin lista negra" (C es obligatorio: el gate de ficha ya lo exige aguas arriba) · vídeo mudo (sin subtítulos) → Q2 N/A · CTA omitido por su agente (skip auditado) → Q3 N/A pero Q9 warn si la policy lo pedía · asset de biblioteca renombrado entre revisiones → Q1 block no corregible (huele a ficha desactualizada, humano decide) · pieza más corta que `min_s` porque el bruto no daba para más → block con evidencia (manual §4: "el bruto no da para el objetivo — decirlo claro") · dos findings sobre el mismo elemento → un solo fix · loop pasada 2 introduce un nuevo block (p.ej. quitar música rompe otra regla) → failed, no pasada 3 · IR ya con revisión QA (re-run) → re-audita sobre la última revisión, no duplica.

## 8. Riesgos
**(a) Desviación honesta del plan**: el plan dibujaba "QA fail → vuelve al agente responsable" como bucle del grafo; el PipelineEngine es lineal por diseño (D2). Propongo el loop DENTRO del handler de qa (sub-cadena en memoria) — mismo efecto, cero cambios al motor. Alternativa descartada: saltos atrás en el grafo (rompe D2 y el determinismo del orden topológico). **(b)** Checks léxicos (Q4/Q5/Q10) tienen falsos negativos obvios (parafraseo de claims) — v1 asume matching literal, honesto y auditable; semántica = post-MVP con LLM y presupuesto (lo decide el learning). **(c)** Quitar música/CTA por QA puede dejar la pieza "peor pero legal" — correcto por diseño: la estética la juzga la puerta humana de preview, la legalidad el QA. **(d)** Q2 con transcripts largos: coste O(n·m) trivial a estas escalas.

## 9. Tests
Engine (~18): Q1 asset no trazable → block+fix DROP · Q2 subtítulo parafraseado → block (y literal → pass; `[inaudible]` → pass) · Q3 CTA no aprobado → block+DROP_CTA · Q4 palabra de blacklist en subtítulo → block · Q5 "GHL" y "99€" en texto → block · Q6 fuera de rango → block · Q7 sin hook → warn · Q8 mandatory sin outro → block · Q9 markers ausentes → warn · Q10 never_do → block · report pass → revisión 8 con Decision · loop: finding corregible → re-ejecución con constraints → pass en pasada 2 (y el agente anota "vetado por QA") · loop que no converge → failed con informe · grafo 12 fases ordenado · golden e2e ampliado (qa pass, rev 8, 8 checkpoints, render renderiza rev 8). Contracts: 0 nuevos.

## 10. Plan implementación
1) Normalizador de texto + QAReport/QAConstraints (TDD) → 2) checks Q1–Q10 uno a uno (TDD, un test por regla) → 3) `apply_verdict` (rev 8) → 4) constraints en agentes F4 (parámetro opcional, TDD por agente) → 5) handler `qa` con loop acotado + grafo 12 → 6) golden e2e (rev 8, 8 checkpoints) → 7) ruff/tests/doc cierre/BITACORA/commit+push.

## 11. Docs/pendientes
- **Para tu validación**: (a) ¿OK el loop dentro del handler (no tocar el motor D2)? (b) ¿OK que QA apruebe con revisión propia (rev 8) y el render renderice esa? (c) ¿fixes v1 solo sustractivos (DROP_*) — confirmar que nunca queremos auto-sustitución?
- Checks con visión (personas autorizadas E, calidad visual) → post-MVP (requiere frames renderizados).
- Matching semántico de claims (parafraseo) → post-MVP, con LLM presupuestado.
- Tras M12: **HITO MVP** — bruto real de cliente Cliender → preview → validación de Toni/equipo media ANTES de F6.

## 12. Cierre
_(se rellena al cerrar el módulo, tras tu OK)_
