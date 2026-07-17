# M8 · F4 Capas de producción — Subtitle Agent + Branding Agent (v1)

> VIOS · 2026-07-17 · KAREN (Fable 5) · Estado: **CERRADO** (aprobado por Nico con ajustes a/b/c; ver §12)

## 1. Objetivo
Primeras capas de producción sobre la Timeline IR: subtítulos word-timed literales del transcript (Subtitle Agent) y branding del cliente — logo, estilo de subtítulos con paleta exacta, intro/outro (Branding Agent). Ambos son **deterministas (sin LLM)** y añaden revisiones vía `TimelineDraft.commit` con Decision auditada. Prerequisito: extender `TimelineDraft` con `add_clip_effect` y `set_clip_transform` (hoy no existen).

## 2. Requisitos funcionales
- **TimelineDraft ext**: `add_clip_effect(track_id, clip_id, effect)` y `set_clip_transform(track_id, clip_id, transform)` mutan clips existentes (KeyError si no existen); ids deterministas intactos.
- **SubtitleAgent**: entrada IR + MediaIntelligence por asset + `SubtitlePolicy` (playbook) + `SubtitleStyle` (ClientProfile.visual). Para cada clip de video, mapea las words del transcript cuyo rango cae dentro de `[in_point, out_point]` del source a frames de timeline. Produce track `subtitle` con clips por línea (agrupación por max chars) o por palabra si `karaoke=true`. Texto = transcript **literal**; segmentos `low_confidence` se incluyen con flag, nunca se corrigen ni inventan.
- **BrandingAgent**: entrada IR + ClientProfile + Playbook. Track `graphic` con clip de logo (esquina segura, opacidad configurable) durante todo el vídeo; aplica `subtitle_style` del cliente (font, `color_base`/`color_emphasis` hex exactos de la paleta, position, uppercase) como effect sobre los clips de subtítulo; inserta intro/outro si `intro_outro.mandatory`.
- **Pipeline**: fases nuevas `subtitle` y `branding` en `vios_default_graph` con dep sobre `edit` (subtitle→branding, branding necesita los clips de subtítulo ya creados). Checkpoint IR por revisión en cada fase.

## 3. No funcionales
Cero LLM/ML (100% determinista y reproducible); cada agente = exactamente 1 revisión con Decision (`by`, `why`, `action`); anti-alucinación estricta (subtítulos = transcript literal; branding solo assets/valores reales de la ficha, hex exactos); testeable sin ffmpeg/whisper (MediaIntelligence fake en memoria).

## 4. Diseño
- `vios_engine/agents/subtitle.py` (`SubtitleAgent`) y `agents/branding.py` (`BrandingAgent`).
- **Vocabulario de effects cerrado** (constantes en contracts, no strings ad-hoc): `subtitle_style` (params: font, color_base, color_emphasis, position, uppercase, size_rel), `karaoke` (params: words con `[{text, start_f, end_f}]`), `logo_overlay` (params: file, corner, margin_rel).
- **Unidades**: la regla "conversión s→frames la hace SOLO el Edit Agent" se generaliza a "**una única función de conversión**": se extrae `s_to_frames(s, fps)` a `vios_contracts.timeline_ops`, la usan Edit Agent y los agentes F4. Nunca conversión ad-hoc inline. ⚠️ Cambio de regla del CLAUDE.md — requiere OK explícito de Nico (ver §8).
- Mapeo transcript→timeline: word en segundos del source → frame del source (`s_to_frames`) → si `in_point ≤ f < out_point` → frame timeline = `clip.start + (f - in_point)`. Palabra que cruza el corte se recorta al clip.
- Layout: constantes de safe-area por plataforma (9:16: subtítulos ~72% altura, logo margen 4%) en un módulo `layout.py`; no números mágicos dispersos.

## 5. Interfaces
`SubtitleAgent.add_subtitles(ir, intel_by_asset: dict[str, MediaIntelligence], playbook, profile) -> TimelineIR` · `BrandingAgent.apply_branding(ir, profile, playbook) -> TimelineIR` · `TimelineDraft.add_clip_effect(track_id, clip_id, effect: dict) -> None` · `TimelineDraft.set_clip_transform(track_id, clip_id, transform: dict) -> None` · fases pipeline: `PhaseHandler` estándar (devuelven `ir` → checkpoint automático).

## 6. Modelos de datos
Sin contratos nuevos. Clip de subtítulo: `source` = texto literal de la línea; timing en `start/in_point/out_point` (frames); estilo y karaoke en `effects[].params`. Logo: clip en track `graphic` con `source` = file del `LogoRef` + `logo_overlay`. Decisiones: 1 por agente (ej. `agent="subtitle", why="subtítulos karaoke desde transcript es-ES (142 words, 2 low_confidence)"`).

## 7. Casos límite
Transcript vacío o `subtitles.enabled=false` → no se crea track, Decision lo anota igualmente (skip auditado) · segmento `low_confidence` → se subtitula literal + `params.low_confidence=true` · palabra cruza límite de clip → recortada; si queda <1 frame, se omite · perfil sin `subtitle_style` → defaults del playbook + Decision lo anota · `visual.logos` vacío → branding sin logo, anotado · `intro_outro.mandatory=true` sin `file` → **error explícito** (gate NEEDS_INPUT, nunca inventar asset) · track subtitle ya existente (re-run) → error, las fases no son idempotentes sobre la misma revisión.

## 8. Riesgos
**(a) Regla de unidades**: mover la conversión a helper único de contracts toca una regla escrita del CLAUDE.md → decidir con Nico antes de codificar (alternativa: Edit Agent pre-materializa el mapeo source↔timeline en `meta`, más acoplado y frágil). **(b)** Validación estética real imposible hasta F5 (render); mitigación: golden IR con snapshot JSON del track de subtítulos. **(c)** Catálogo de effects puede quedarse corto en M9/M10; mitigación: constantes centralizadas + `Effect.params` libre da margen sin romper schema.

## 9. Tests
Contracts (~8): `add_clip_effect`/`set_clip_transform` happy + clip/track inexistente + commit sube revisión + base intacta; `s_to_frames` bordes. Engine (~14): SubtitleAgent — texto literal exacto (anti-alucinación), agrupación líneas por max chars, karaoke por palabra, low_confidence flag, mapeo frames con clip recortado (in_point>0), transcript vacío, enabled=false; BrandingAgent — logo con transform correcto, estilo con hex exactos de paleta, sin logos, intro/outro mandatory sin file → error; pipeline — grafo con fases nuevas ordenado, e2e golden brief → IR revisión 3 (edit→subtitle→branding) con checkpoints por revisión.

## 10. Plan implementación
1) `TimelineDraft` ext + `s_to_frames` (TDD, contracts) → 2) catálogo effects + layout constants → 3) SubtitleAgent (TDD) → 4) BrandingAgent (TDD) → 5) fases en grafo + golden e2e → 6) ruff limpio + suite verde + commit + push. Cierre: doc a v2 CERRADO + entrada BITACORA.

## 11. Docs/pendientes
- Safe-areas definitivas por plataforma (TikTok/IG UI overlap) — validar en F5 con render real.
- M9 consumirá `set_clip_transform` (zooms/reframe) y M10 `add_clip_effect` — la extensión del draft se diseñó genérica para ambos; `source_frame_to_timeline` compartido (ducking M9, b-roll M10).
- La ficha (`IntroOutro`) no distingue intro de outro (un solo `file`): **pendiente confirmar con Nico** si el bumper único como OUTRO al final es la semántica correcta o hay que ampliar el contrato B.visual.

## 12. Cierre (como quedó implementado — 2026-07-17)
- §8(a) resuelto: **opción A** aprobada. `s_to_frames`/`frames_to_s` + `source_frame_to_timeline(ir, asset_id, source_frame) -> int | None` en `vios_contracts.timeline_ops`. Regla del CLAUDE.md actualizada con la redacción de Nico.
- Ajuste (a): el SubtitleAgent aplica TODO el estilo; BrandingAgent no toca el track subtitle (test lo garantiza).
- Ajuste (b): palabra que no cabe entera en el clip se OMITE (nunca texto sin su audio); segmentos sin word-timing se clampan al rango visible.
- Ajuste (c): grafo `ingest → director → story → edit → subtitle → branding`; branding parte de `ctx.ir` subtitulada; 1 revisión + Decision + checkpoint por fase.
- Desviación menor vs §4: `karaoke` no es effect type propio — va como flag en `params` de `subtitle_style` (en karaoke el clip ES la palabra; un type extra era redundante). Catálogo v1: `EFFECT_SUBTITLE_STYLE`, `EFFECT_LOGO_OVERLAY` (`effects.py`, contracts).
- Intro/outro: materializado como **outro al final** con duración REAL de su MediaIntelligence; `mandatory` sin file o sin análisis → error `NEEDS_INPUT` (nunca se inventa duración). Sin shift de timeline (no hay intro hasta que la ficha lo distinga).
- Tests: contracts 33→43 · engine 61→74 (13 nuevos M8 + golden e2e F4 con 3 checkpoints). Ruff limpio.
