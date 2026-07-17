# DISEÑO M1 — Timeline IR (F1 Contratos)

> **Módulo:** M1 · **Fase:** F1 · **Versión:** v1 · **Fecha:** 2026-07-16
> **Autor:** KAREN (Opus 4.8) · **Plan padre:** `260716_PLAN_video-intel-os_v1.md` (D1, riesgo #1)
> **Estado:** DISEÑO + IMPLEMENTACIÓN (Nico dio confianza para avanzar en la misma sesión)
> **Criticidad:** MÁXIMA — es el contrato central. Si la IR está mal, todo refactoriza en cascada.

---

## 1. Objetivo

Definir e implementar la **Timeline IR**: la representación intermedia declarativa de una edición. Es el único punto de verdad sobre "qué se edita". Los agentes la producen y consumen; el render la materializa. M1 entrega: modelos tipados (Pydantic v2), JSON Schema exportado y versionado, y una librería de operaciones puras (`create`, `draft/commit`, `diff`, `validate`, serialización), con golden tests que la fijan contra casos reales.

**No incluye:** render, agentes, ni lógica de edición inteligente. Solo el contrato + sus operaciones mecánicas.

---

## 2. Requisitos funcionales

- **RF1** — Crear una IR vacía válida: `create_timeline(project_id, fps, canvas, platform, playbook)` → revisión 0, sin tracks.
- **RF2** — Modelo de datos completo: tracks (video/audio/subtitle/graphic) → clips (source, in/out, start, transform, effects), markers (beat/hook/cta), meta (platform, playbook, decisions auditables).
- **RF3** — **Inmutabilidad por revisión.** Una IR comprometida es de solo lectura. Cambios se hacen sobre un `TimelineDraft` (copia mutable) y `commit(by, why)` produce una NUEVA IR con `revision+1`, `parent_revision` enlazado y un `Decision` anotado (quién + por qué). La IR original nunca muta.
- **RF4** — IDs **deterministas** (secuenciales por tipo: `v0/v1`, `c0/c1`, `m0/m1`). Sin UUID/random → golden tests estables.
- **RF5** — `validate(ir)`: valida tipos (Pydantic) + semántica (out>in, frames≥0, fps>0, canvas>0, clips referencian tracks existentes, markers dentro de rango, revisión coherente).
- **RF6** — `diff(ir_a, ir_b)`: lista estructural de cambios (add/remove/modify sobre tracks/clips/markers) entre dos revisiones. Determinista y legible.
- **RF7** — Serialización canónica: `to_json(ir)` / `from_json(str)` con round-trip exacto. Claves ordenadas para diffs estables.
- **RF8** — Export de **JSON Schema** a `packages/contracts/schemas/timeline_ir.schema.json` (regenerable, versionado en git).

## 3. Requisitos no funcionales

- **RNF1 · Time unit = frames (int).** Canónico, determinista, sin drift float. `fps` en la raíz convierte a segundos en el render. Posición y duración siempre en frames.
- **RNF2 · Versionado desde día 1.** `schema_version` semántico (`1.0.0`). Cambios de contrato → bump + nota de migración.
- **RNF3 · Cero dependencias pesadas.** Solo Pydantic v2. La librería es pura (sin I/O salvo helpers explícitos de fichero para el schema).
- **RNF4 · Auditable.** Cada revisión responde "quién la hizo y por qué" vía `Decision`. Trazable end-to-end (base del debugging y del learning loop).
- **RNF5 · Testeable sin render.** Toda la lógica se valida en memoria; los golden tests no tocan FFmpeg/Remotion.

---

## 4. Diseño

### 4.1 Jerarquía de modelos (todos frozen)
```
TimelineIR
├── schema_version: str = "1.0.0"
├── project_id: str
├── revision: int = 0
├── parent_revision: int | None
├── fps: int
├── canvas: Canvas { width, height, aspect }      # aspect ej. "9:16"
├── tracks: list[Track]
│     └── Track { id, kind: video|audio|subtitle|graphic, clips: list[Clip] }
│           └── Clip { id, source, start, in_point, out_point,
│                      transform: Transform, effects: list[Effect] }
├── markers: list[Marker]                           # Marker { id, kind: beat|hook|cta, at, label, payload }
└── meta: Meta { platform, playbook, decisions: list[Decision] }
                                                     # Decision { revision, agent, why, action }
```
- **Transform** `{ scale=1.0, x=0, y=0, rotation=0.0, opacity=1.0 }` — reframe 9:16, zoom, etc.
- **Effect** `{ type: str, params: dict }` — genérico; el catálogo cerrado se define en agentes (F4).
- **Clip.source** — para video/audio = `asset_id`; para subtitle/graphic = texto o ref de recurso.

### 4.2 Patrón draft/commit (inmutabilidad)
```python
draft = TimelineDraft.from_ir(ir)          # deep copy mutable
tid = draft.add_track("video")
draft.add_clip(tid, source="a1", start=0, in_point=0, out_point=90)
draft.add_marker("hook", at=0, label="Hook 1.5s")
new_ir = draft.commit(by="edit-agent", why="Timeline v1: 3 cortes + hook")
# ir intacta (revision 0); new_ir.revision == 1, parent_revision == 0,
# new_ir.meta.decisions[-1] == Decision(revision=1, agent="edit-agent", why=...)
```
La revisión sube **una vez por commit** (una transacción de agente), no por cada clip. Coherente con §2.3 del plan ("cada flecha = una revisión").

### 4.3 Módulos de código (`packages/contracts/src/vios_contracts/`)
| Fichero | Contenido |
|---|---|
| `timeline_ir.py` | Modelos frozen (TimelineIR, Track, Clip, ...) + `create_timeline` |
| `timeline_draft.py` | `TimelineDraft` (builder mutable + `commit`) |
| `timeline_ops.py` | `validate`, `diff`, `to_json`, `from_json` |
| `schemas/timeline_ir.schema.json` | JSON Schema exportado (regenerable con `scripts/export_schema.py`) |

`__init__.py` reexporta la API pública. Se sustituye el stub de M0.

---

## 5. Interfaces (API pública)

```python
create_timeline(project_id, fps, canvas, platform, playbook) -> TimelineIR
TimelineDraft.from_ir(ir) -> TimelineDraft
  .add_track(kind) -> track_id
  .add_clip(track_id, source, start, in_point, out_point, transform=None, effects=None) -> clip_id
  .add_marker(kind, at, label="", payload=None) -> marker_id
  .remove_clip(track_id, clip_id) / .remove_track(track_id) / .remove_marker(marker_id)
  .commit(by, why) -> TimelineIR         # nueva revisión inmutable
validate(ir) -> None                      # raise TimelineValidationError
diff(ir_a, ir_b) -> list[Change]          # Change { op, path, before, after }
to_json(ir) -> str  /  from_json(s) -> TimelineIR
export_json_schema(path) -> None
```

Sin dependencia de engine/DB: la librería es autónoma (la usa engine, mcp-server y render vía JSON).

---

## 6. Modelos de datos

Ya detallados en §4.1. Notas de campo:
- `Clip.start` = frame de inicio en la timeline; `in_point/out_point` = recorte dentro del source (frames). Duración = `out_point - in_point`.
- `Decision` es append-only; nunca se borra (audit). Acumula el historial completo dentro de `meta.decisions`.
- Persistencia: la IR completa va al campo `timelines.ir jsonb` (tabla de M0), una fila por revisión.

---

## 7. Casos límite

- **CL1** — `out_point <= in_point` → `TimelineValidationError`.
- **CL2** — Clip en track inexistente → error de validación.
- **CL3** — Frames negativos (start/at/in/out < 0) → error.
- **CL4** — IR vacía (0 tracks) → **válida** (estado inicial legítimo).
- **CL5** — Solapamiento de clips en un mismo track → **permitido** en M1 (lo resuelve el Edit Agent); documentado, no bloqueante.
- **CL6** — `commit` sin cambios respecto al draft base → permitido, crea revisión "no-op" con su decisión (útil para anotar aprobaciones).
- **CL7** — `diff` entre revisiones no consecutivas → funciona (compara estado, no historial).
- **CL8** — Round-trip JSON de floats en Transform → usar repr estable; frames son int (sin problema).

---

## 8. Riesgos

| Riesgo | Prob. | Mitigación |
|---|---|---|
| IR incompleta → refactor en cascada (riesgo #1 del plan) | Media | Validar contra 3 casos reales (reel corto, podcast→clip, carrusel-vídeo) en golden tests ANTES de F2 |
| Frames vs segundos mal elegido | Baja | Frames canónico (RNF1); fps en raíz; decisión documentada |
| `effects.params` como dict libre → caos futuro | Media | Aceptado en M1 (YAGNI); catálogo cerrado se tipa en F4 cuando existan los agentes que los emiten |
| Golden tests frágiles por IDs random | — | IDs deterministas (RF4) — mitigado por diseño |

---

## 9. Tests (TDD, golden-first)

- **T1** — `create_timeline` → revisión 0, 0 tracks, `validate` ok.
- **T2** — draft add track/clip/marker → `commit` → revisión 1, `parent_revision=0`, decisión anotada, **IR original intacta**.
- **T3** — inmutabilidad: intentar mutar una IR comprometida lanza error (frozen).
- **T4** — `validate` rechaza CL1/CL2/CL3; acepta CL4 (vacía).
- **T5** — `diff(rev0, rev1)` lista los adds correctos; `diff(ir, ir)` vacío.
- **T6** — round-trip `to_json`/`from_json` == original (igualdad estructural).
- **T7** — `export_json_schema` produce JSON con claves esperadas (`tracks`, `markers`, `meta`, `schema_version`).
- **T8 (golden)** — construir 3 timelines de referencia (reel educativo, podcast→clip, carrusel-vídeo), volcar JSON y comparar contra ficheros golden en `tests/golden/`. Regenerables con flag, pero cambios requieren revisión humana.

Cobertura objetivo M1: **≥90%** (es el núcleo; se exige rigor).

---

## 10. Plan de implementación (orden TDD)

1. Escribir tests T1–T7 (rojos) sobre la API objetivo.
2. `timeline_ir.py`: modelos frozen + `create_timeline`.
3. `timeline_draft.py`: builder + `commit` (deep copy, bump revisión, append Decision).
4. `timeline_ops.py`: `validate`, `diff`, `to_json`/`from_json`.
5. `scripts/export_schema.py` + generar `schemas/timeline_ir.schema.json`.
6. Verde T1–T7 → construir 3 golden timelines → T8.
7. `uv run pytest` + `ruff` verde → cobertura ≥90%.
8. Cierre: doc, BITACORA, memoria; commit.

---

## 11. Documentación / cierre

- Este doc en `01. MODULOS/`.
- Docstrings en cada módulo + ejemplos en `__init__`.
- `schemas/timeline_ir.schema.json` versionado (fuente de verdad del contrato para consumidores no-Python, ej. render-svc Node).
- BITACORA entrada M1; memoria `project_vios_plan.md` → estado F1/M1.
- Commit en `~/dev/vios/`.

---

## Salida esperada M1 (criterio de cierre)

✅ Modelos frozen + `create/draft/commit/diff/validate/serialize` implementados · ✅ JSON Schema exportado y versionado · ✅ IDs deterministas · ✅ tests T1–T8 verdes con 3 golden reales · ✅ cobertura ≥90% · ✅ IR validada contra 3 casos reales antes de F2.

---

*Próximo tras M1: M2 · ClientProfile + Playbook (schemas + loader YAML + 2 playbooks semilla + 1 cliente semilla con branding real Cliender).*
