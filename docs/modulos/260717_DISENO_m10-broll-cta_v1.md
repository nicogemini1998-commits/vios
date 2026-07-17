# M10 · F4 Capas de producción — B-Roll Agent + CTA/Thumbnail Agent (v1)

> VIOS · 2026-07-17 · KAREN (Fable 5) · Estado: **CERRADO** (§6 aprobado por Nico a posteriori el 2026-07-17; cierre en §12)

## 1. Objetivo
Última pareja de capas F4 (cierra la fase): **BRollAgent** (inserta b-roll EXISTENTE de la biblioteca del cliente en los valles de voz — nunca genera material) y **CTAThumbnailAgent** (overlay de CTA con el copy real de la ficha + candidato de thumbnail como anotación en la IR para que F5 lo extraiga). Deterministas y sin LLM, como M8/M9 — el plan preveía LLM+embeddings/visión; v1 sigue el patrón F4 de regla fija auditable y la selección "inteligente" llega con learning (H).

## 2. Requisitos funcionales
- **BRollAgent** — entrada IR + intel_by_asset + Playbook + ClientProfile (`Library.broll` F):
  - **Valles**: rangos SIN voz dentro de los clips de vídeo cuyo source TIENE transcript con segmentos (así el outro del branding y material sin habla no se tapan). Valle = hueco ≥ `BROLL_MIN_VALLEY_S` entre rangos de voz remapeados a timeline. El tramo de hook (primeros `hook.max_seconds` del playbook) queda protegido: ahí siempre se ve al speaker.
  - **Inserción**: track vídeo nuevo (overlay). Assets de `library.broll` en orden, round-robin determinista. Solo assets con MediaIntelligence (duración real); sin análisis → se salta ese asset anotado. Cubre `min(duración_asset, valle)`. Con dims reales → transform cover al canvas (misma fórmula que M9); sin dims → clip sin transform + nota (nunca escalar a ciegas). Sin biblioteca → skip anotado (no bloqueante, como música).
- **CTAThumbnailAgent** — entrada IR + Playbook (`CTAPolicy`) + ClientProfile (`Audience.cta` D, `VisualIdentity` B):
  - **CTA**: si `cta.enabled` → overlay graphic desde el marker `cta` (que puso el Edit Agent) hasta el fin de la timeline. Copy = `audience.cta.text` de la ficha; fallback `cta.default_text` del playbook; sin texto en ninguno → skip anotado (no se inventa copy). Effect `cta_overlay` con text, destination, font (usage "cta" de la ficha, si hay) y color (rol "accent" de la palette, si hay) — campos vacíos si la ficha no los tiene, jamás aproximados.
  - **Thumbnail**: marker `thumbnail` (kind nuevo) con payload `{asset_id, source_frame_s → frame}`. Candidato determinista: punto medio del rango del mejor hook (payload del marker `hook`); sin hook → punto medio del primer clip de vídeo. F5 extrae el frame; VIOS solo lo anota.
- **Pipeline**: fases `broll` (deps `audio`) y `cta` (deps `broll`) cierran el grafo → 10 fases; 1 revisión + Decision + checkpoint cada una.

## 3. No funcionales
Determinista/reproducible (cero LLM/random); anti-alucinación (solo assets reales de `library.broll`, duraciones/dims de MediaIntelligence, copy solo de ficha/playbook); testeable en memoria; no tocan tracks subtitle ni audio ni el vídeo base (b-roll y CTA son SIEMPRE capas nuevas encima).

## 4. Diseño
- `vios_engine/agents/broll.py` (`BRollAgent.apply_broll(ir, intel_by_asset, playbook, profile)`) y `agents/cta.py` (`CTAThumbnailAgent.apply_cta(ir, playbook, profile)`).
- **Promoción prevista en M9 §11**: el helper voz-en-timeline sale de `agents/audio.py` a `vios_contracts.timeline_ops` como `speech_ranges_in_timeline(ir, intel_by_asset)` (remapea clip a clip, clampea, fusiona). AudioMusicAgent pasa a consumirlo; BRollAgent usa su complemento.
- Catálogo effects: `EFFECT_CTA_OVERLAY` ("cta_overlay", params: text, destination, position, font, color). `KNOWN_EFFECTS` pasa a 5.
- Constantes en `layout.py`: `BROLL_MIN_VALLEY_S = 1.0` + helper `cover_scale(canvas_w, canvas_h, src_w, src_h)` compartido con visual.py (misma fórmula, un solo sitio).
- Limpieza de regla: `edit.py` aún tenía `_to_frames` inline (pre-M8); pasa a `s_to_frames` canónico.

## 5. Interfaces
`BRollAgent.apply_broll(ir, intel_by_asset, playbook, profile) -> TimelineIR` · `CTAThumbnailAgent.apply_cta(ir, playbook, profile) -> TimelineIR` · fases `broll`/`cta` como `PhaseHandler` estándar sobre `ctx.ir`.

## 6. Modelos de datos
**Cambios de contrato (aditivos, requieren tu OK — igual que width/height en M9):** (a) `MarkerKind` gana `"thumbnail"` (Literal ampliado, sin ruptura); (b) effect nuevo `cta_overlay` en el catálogo; (c) promoción de `speech_ranges_in_timeline` a `timeline_ops` (ya pactada en M9 §11). Sin campos nuevos en fichas/playbooks: todo lo que necesitan ya existe (`Library.broll`, `Audience.cta`, `CTAPolicy`, `FontRef.usage`, `ColorToken.role`).

## 7. Casos límite
`library.broll` vacía → skip anotado (no NEEDS_INPUT: b-roll no bloqueante) · asset b-roll sin MediaIntelligence → se salta, se prueba el siguiente, anotado · ningún valle ≥ mínimo → skip "sin valles" · vídeo mudo (sin transcript) → sin valles computables → skip (no se tapa un vídeo que no entendemos) · valle más largo que el asset → cubre lo que dura el asset · b-roll sin dims → sin transform + nota · `cta.enabled=false` → skip auditado · sin texto CTA en ficha NI playbook → skip anotado (no se inventa copy) · sin marker `cta` → overlay en los últimos frames según `position` de la policy · timeline vacía → ambos skip · sin hook → thumbnail del primer clip; sin clips → sin thumbnail, anotado.

## 8. Riesgos
**(a)** B-roll determinista "primer asset que quepa" puede quedar temáticamente irrelevante — mitigación: `Asset.description` existe en la ficha; matching semántico llega con learning/embeddings (post-MVP), v1 es honesto y auditable. **(b)** Tapar al speaker en momentos clave — mitigación: hook protegido + solo valles sin voz. **(c)** Thumbnail sin visión puede no ser el frame más vendedor — v1 usa el hook (ya scoreado por Story); visión llega en F5+. **(d)** `MarkerKind` ampliado obliga a exportar de nuevo el JSON Schema — se regenera en este módulo.

## 9. Tests
Contracts (~3): `speech_ranges_in_timeline` (remap+clamp+fusión, segmento que cruza corte), marker `thumbnail` válido en la IR, `cta_overlay` en catálogo. Engine (~15): BRoll — valles rellenados con assets reales round-robin, valle < mínimo ignorado, hook protegido, biblioteca vacía → skip, asset sin análisis → siguiente, sin dims → sin transform+nota, no toca subtitle/audio/vídeo base, outro sin transcript no se tapa, vídeo mudo → skip; CTA — copy de la ficha, fallback playbook, sin texto → skip, disabled → skip, thumbnail desde hook (punto medio), sin hook → primer clip, effect con font/color de la ficha; pipeline — grafo 10 fases ordenado, golden e2e (revisión 7, decisiones edit→subtitle→branding→visual→audio→broll→cta, 7 checkpoints).

## 10. Plan implementación
1) Contratos: MarkerKind+thumbnail, `cta_overlay`, `speech_ranges_in_timeline` + refactor audio.py (TDD contracts) → 2) `cover_scale` + constante en layout.py + refactor visual.py → 3) BRollAgent (TDD) → 4) CTAThumbnailAgent (TDD) → 5) grafo 10 fases + golden e2e ampliado + export schema → 6) ruff + doc cierre + BITACORA + commit + push.

## 11. Docs/pendientes
- Selección de b-roll por relevancia semántica (embeddings sobre `Asset.description` + transcript del valle) — post-learning H.
- Thumbnail con visión (frames candidatos scoreados) — F5+, cuando haya extracción real de frames.
- CTA multi-plataforma (copy por plataforma) — cuando `Audience.cta` se amplíe.

## 12. Cierre (como quedó implementado — 2026-07-17; §6 APROBADO por Nico: "aditivos, luz verde, decisión A bien implementada")
- §6 aplicado: `MarkerKind` + `"thumbnail"` (schema JSON regenerado), effect `cta_overlay` (catálogo = 5), `speech_ranges_in_timeline` promocionado a `timeline_ops` (audio M9 refactorizado a consumirlo, lógica idéntica, tests M9 intactos).
- Limpiezas de regla: `edit.py` usaba `_to_frames` inline (pre-M8) → `s_to_frames` canónico; fórmula cover extraída a `cover_scale()` en `layout.py` (visual M9 + broll M10 la comparten). Constantes nuevas: `BROLL_MIN_VALLEY_S=1.0`, `CTA_DURATION_S=3.0`.
- BRollAgent: valles = complemento de la voz SOLO en clips con transcript (outro/material mudo no se tapan), hook protegido (`hook.max_seconds`), round-robin sobre assets analizados (sin análisis → descartado y anotado), cover con dims reales (sin dims → sin transform + nota), track vídeo overlay nuevo.
- CTAThumbnailAgent: copy ficha > playbook > skip; overlay de 3s anclado al marker `cta` clampeado al fin; params con font usage "cta" y color rol "accent" de la ficha (vacíos si no hay). Thumbnail = marker con `{asset_id, source_frame}`: punto medio del hook, fallback punto medio del primer clip; `at` remapeado a timeline.
- Grafo 10 fases: `…→ audio → broll → cta`; golden e2e = revisión 7, 7 checkpoints, decisiones edit→subtitle→branding→visual→audio→broll→cta, CTA con copy real de la ficha + marker thumbnail presente.
- Tests: contracts 45→50 (5 nuevos M10) · engine 89→106 (17 nuevos M10 + golden/grafo ampliados). Ruff limpio. **F4 COMPLETA (11/14 módulos). Próximo: M11 Render Service (F5).**
