# M9 · F4 Capas de producción — Visual/Motion Agent + Audio/Music Agent (v1)

> VIOS · 2026-07-17 · KAREN (Fable 5) · Estado: **CERRADO** (aprobado por Nico; cierre en §12)

## 1. Objetivo
Segunda pareja de capas F4 sobre la Timeline IR, deterministas y sin LLM: **VisualMotionAgent** (reframe 9:16 del bruto horizontal + zooms de ritmo según pacing) y **AudioMusicAgent** (música de la biblioteca REAL del cliente + ducking alineado a la voz). Cada agente = 1 revisión con Decision, vía `TimelineDraft`, consumiendo la aritmética canónica (`s_to_frames`) y el remapeo compartido (`source_frame_to_timeline`) de M8.

## 2. Requisitos funcionales
- **VisualMotionAgent** — entrada IR + intel_by_asset + Playbook (`PacingPolicy`) + ClientProfile (`Pacing` E):
  - **Reframe**: si el source no es del aspect del canvas (ej. 16:9 → 9:16), `set_clip_transform` en cada clip de vídeo con scale de cover centrado (`scale = max(cw/sw, ch/sh)` relativo, x=y=0 centrado). Necesita width/height del source (ver §6/§8). Si el source ya encaja → no tocar.
  - **Zooms**: solo si `pacing.zoom=true` (playbook) o `profile.edit_rules.pacing.zooms=true`. Regla determinista v1: zoom-in sutil en clips cuyo `start` coincide con marker `beat`, alternando intensidad (par → 1.00→1.05, impar → 1.05→1.00) escalada por `cut_style` (calm 0.03 / medium 0.05 / aggressive 0.08). Effect `zoom` con `add_clip_effect`. Cero criterio estético inventado por LLM: la regla es fija y auditable.
- **AudioMusicAgent** — entrada IR + intel_by_asset + Playbook (`MusicPolicy`) + ClientProfile (`MusicRules` E + `Library.music_sfx` F):
  - **Música**: si `music.enabled` y `library.music_sfx` tiene assets → track `audio` nuevo con el PRIMER asset de la biblioteca (v1; selección por estilo llega con learning), `out_point = min(duración_real_música, fin_timeline)`. Duración real de su MediaIntelligence — sin análisis, no se añade (skip anotado). Sin looping en v1.
  - **Ducking**: si `music.ducking` → rangos de voz en timeline = segmentos del transcript remapeados clip a clip con `source_frame_to_timeline` (inicio y fin clampeados al clip), fusionando solapes/adyacentes. Effect `music_mix` sobre el clip de música: `{volume_rel, target_lufs, ducking: true, duck_ranges: [{start, end}]}` (frames de timeline).
- **Pipeline**: fases `visual` (deps `branding`) y `audio` (deps `visual`) al final del grafo; 1 revisión + Decision + checkpoint cada una.

## 3. No funcionales
Determinista y reproducible (cero LLM/ML, cero random); anti-alucinación (solo assets de `library.music_sfx`, duraciones/dimensiones reales de MediaIntelligence, nunca inventadas); testeable en memoria (intel fake); los agentes NO tocan tracks subtitle/graphic ni el audio de voz existente.

## 4. Diseño
- `vios_engine/agents/visual.py` (`VisualMotionAgent.apply_motion(ir, intel_by_asset, playbook, profile)`) y `agents/audio.py` (`AudioMusicAgent.apply_music(ir, intel_by_asset, playbook, profile)`).
- Catálogo effects ampliado en `vios_contracts.effects`: `EFFECT_ZOOM` (params: scale_from, scale_to) y `EFFECT_MUSIC_MIX` (params: volume_rel, target_lufs, ducking, duck_ranges). `KNOWN_EFFECTS` pasa a 4.
- Intensidades de zoom por `cut_style` como constantes en `layout.py` (sin números mágicos).
- Voz-en-timeline como helper privado del AudioMusicAgent (itera clips de vídeo × segmentos, remapea extremos con `source_frame_to_timeline`, fusiona intervalos) — si M10 lo necesita (b-roll en valles = complemento de estos rangos), se promociona a `timeline_ops` en ese momento, no antes.
- El reframe usa `set_clip_transform` (estado estático); el zoom usa `add_clip_effect` (animación en el tiempo). Un clip puede llevar ambos.

## 5. Interfaces
`VisualMotionAgent.apply_motion(ir, intel_by_asset, playbook, profile) -> TimelineIR` · `AudioMusicAgent.apply_music(ir, intel_by_asset, playbook, profile) -> TimelineIR` · fases `visual`/`audio` como `PhaseHandler` estándar sobre `ctx.ir`.

## 6. Modelos de datos
**Cambio de contrato (requiere tu OK)**: `MediaIntelligence` gana `width: int | None` y `height: int | None` (hoy las dimensiones solo viven en la metadata ffprobe de M3, que no llega a los agentes). Aditivo, `extra="ignore"`, sin ruptura; el analyzer M4 los rellenará desde ffprobe (ajuste menor M4). Sin más contratos nuevos: zooms/mix viven en `Effect.params`.

## 7. Casos límite
Source sin width/height (intel incompleta) → reframe omitido para ese clip + nota en Decision (nunca escalar a ciegas) · aspect ya coincide → sin transform · `zoom=false` en playbook y ficha → sin zooms, anotado · `music.enabled=false` → skip auditado · `music_sfx` vacía → skip anotado "sin música en biblioteca" (no es NEEDS_INPUT: la música no es bloqueante) · música sin MediaIntelligence (duración desconocida) → skip anotado · música más corta que la timeline → cubre lo que dura, sin loop, anotado · ducking sin transcript (vídeo mudo) → música a volumen normal, `duck_ranges=[]` · timeline vacía → ambos agentes skip auditado.

## 8. Riesgos
**(a)** Dimensiones: tocar `MediaIntelligence` + analyzer M4 amplía el alcance de M9 (pequeño pero cruza módulos) — alternativa descartada: pasar la metadata M3 como parámetro extra (acopla la firma de los agentes al repo de assets). **(b)** Zoom determinista puede quedar mecánico visualmente — mitigación: intensidades conservadoras, se calibra con render real en F5 y learning en H. **(c)** `duck_ranges` precomputados engordan params si hay muchos segmentos — aceptable v1 (decenas, no miles); render F5 decide si prefiere sidechain real. **(d)** Elegir "primer asset" de música es arbitrario pero honesto y determinista; selección por `music.style` llega con datos reales de uso.

## 9. Tests
Engine (~14): VisualMotion — reframe 16:9→9:16 (scale cover correcto, centrado), source ya 9:16 sin transform, sin dimensiones → omitido+anotado, zooms en beats alternados con intensidad por cut_style, zoom desactivado → sin effects, no toca subtitle/graphic; AudioMusic — música con duración real (out_point correcto), más corta que timeline, biblioteca vacía → skip, sin análisis → skip, ducking con rangos remapeados y fusionados (incluye segmento que cruza corte → clamp), vídeo mudo → duck_ranges vacío; pipeline — grafo 8 fases ordenado, golden e2e F4 completo (revisión 5, decisiones edit→subtitle→branding→visual→audio, 5 checkpoints). Contracts (~2): dims nuevas en MediaIntelligence + effects nuevos en catálogo.

## 10. Plan implementación
1) Contrato: width/height en MediaIntelligence + effects nuevos (TDD contracts) → 2) analyzer M4 rellena dims (ajuste + test) → 3) VisualMotionAgent (TDD) → 4) AudioMusicAgent (TDD) → 5) fases en grafo + golden e2e ampliado → 6) ruff + doc v1 CERRADO + BITACORA + commit + push.

## 11. Docs/pendientes
- Selección de música por estilo/energía (post-learning, bloque H) — v1 primer asset.
- Looping/fade de música si es más corta que la pieza — decidir en F5 con render real.
- Posible promoción del helper voz-en-timeline a `timeline_ops` cuando M10 (b-roll en valles) lo pida.

## 12. Cierre (como quedó implementado — 2026-07-17)
- §6 aprobado: `MediaIntelligence` ganó `width`/`height` (aditivo); el analyzer M4 los rellena desde la metadata ffprobe (2 líneas + test).
- Además se promocionó `timeline_end(ir)` a `vios_contracts.timeline_ops` (lo usaban branding M8 con helper privado y ahora audio M9) — pequeña desviación aditiva no prevista en §4, coherente con la regla "una sola aritmética".
- VisualMotionAgent: reframe cover centrado con `set_clip_transform` (scale = max(cw/sw, ch/sh), redondeado a 4 decimales); sin dims → omitido y anotado en la Decision; zooms `EFFECT_ZOOM` en clips que arrancan en beat, alternados, intensidad `ZOOM_INTENSITY` en `layout.py` (calm .03 / medium .05 / aggressive .08).
- AudioMusicAgent: primer asset de `music_sfx`, duración real de su MediaIntelligence (sin análisis → skip), sin loop; `EFFECT_MUSIC_MIX` con `volume_rel` (MusicRules), `target_lufs` (policy) y `duck_ranges` remapeados/clampeados/fusionados desde el transcript (vídeo mudo → lista vacía).
- Grafo 8 fases: `…→ branding → visual → audio`; golden e2e termina en revisión 5 con 5 checkpoints y decisiones edit→subtitle→branding→visual→audio.
- Tests: contracts 43→45 · engine 74→89 (14 nuevos M9 + golden ampliado + dims en analyzer). Ruff limpio.
