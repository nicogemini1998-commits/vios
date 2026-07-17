# M11 · F5 Render + QA — Render FFmpeg nativo (IR → filtergraph → preview/masters) (v2)

> VIOS · 2026-07-17 · KAREN (Fable 5) · Estado: **APROBADO por Nico (2026-07-17) — en implementación** (cierre en §12)
> **Decisión §4 (d1) de Nico: OPCIÓN A** — `volume` con `between()` sobre los duck_ranges auditados ("la IR es la verdad", determinismo = idempotencia). `sidechaincompress` DESCARTADO incluso como plan B (recomputaría el ducking en vivo ignorando la Decision de M9 → dos verdades divergentes). **Refinamiento obligatorio**: rampas deterministas en los bordes de cada duck_range dentro de la expresión (attack ~150 ms / release ~300 ms, parametrizable) — se computan de los bordes de los ranges, sigue siendo puro y fiel a la IR.
> Sustituye a `260717_DISENO_m11-render-svc_v1.md` (Remotion) por directiva de Nico: cero atadura de terceros — Remotion exige licencia comercial para empresas del tamaño de HBD; FFmpeg es libre, ya está en el stack (M3) y corre en nuestros contenedores. La arquitectura buena de v1 se mantiene (intérprete genérico data-driven + función pura con golden tests); solo cambia el backend y se colapsa el micro-servicio Node.

## 1. Objetivo
Convertir la Timeline IR (rev 7, 6 capas F4) en vídeo real con **FFmpeg nativo dentro del engine Python**: preview 480p barata primero, masters por plataforma solo tras aprobación (2 puertas del manual), thumbnail del marker M10. Se **elimina `apps/render-svc`** (Node :4011): un solo runtime, menos superficie, más control. Rate limits y escalabilidad van en el diseño desde el día 1, como el TokenBudget en M5.

## 2. Requisitos funcionales
- **`ir_to_filtergraph(ir, asset_paths) -> RenderPlan`** — función PURA (corazón testeable): IR → plan de render ffmpeg (inputs, filter_complex, maps, args de encode). Sin I/O, sin subprocess. Golden tests contra las 3 IR de M1 + la IR rev-7 del e2e ANTES de ejecutar ffmpeg real.
- **Mapping del catálogo cerrado de effects (5, M8–M10) a filtros ffmpeg estándar** (directiva):

  | IR | Filtro ffmpeg |
  |---|---|
  | cortes/clips (video/audio) | `trim`/`atrim` + `setpts`/`asetpts` + `concat` |
  | `Transform` (scale/x/y/rotation/opacity) | `scale` + `crop`/`overlay` (+ `rotate`, `colorchannelmixer` alpha) |
  | `subtitle_style` (líneas y karaoke) | **subtítulos ASS/SSA** generados del track subtitle (karaoke real con tags `\k`, hex/font exactos de params) + filtro `ass` (burn-in) |
  | `logo_overlay` | `overlay` en esquina con margin_rel (safe-areas de `layout.py`) |
  | `zoom` (scale_from→scale_to) | `zoompan` (expresión lineal por frame sobre la duración del clip) |
  | `music_mix` + ducking | `amix` + `loudnorm` (target_lufs) + ducking (ver §4, decisión d1) |
  | `cta_overlay` | `drawtext` (font/color exactos de params) |
  | marker `thumbnail` | `-ss <frame/fps>` + `-frames:v 1` sobre el SOURCE → JPEG |

  Effect fuera del catálogo → **error explícito** (catálogo cerrado, nada se ignora en silencio).
- **Calidades**: `preview` = 480p (scale=-2:480, como el proxy M3), CRF alto, encode rápido · `master` = resolución/bitrate/fps de `PLATFORM_MASTERS` (dato, no código — como `layout.py`): v1 IG/TikTok 1080×1920 9:16 ~10 Mbps 30fps, YouTube 1920×1080 16:9; codec H.264 high + AAC. Añadir plataforma = añadir dato.
- **Cola de render con techo (rate limits, directiva)**: semáforo global `RENDER_MAX_CONCURRENCY` (config, default cores−1) · límite por cliente `RENDER_MAX_PER_CLIENT` (default 1) — un cliente no monopoliza · backpressure FIFO con estado `queued` · **idempotencia**: render ya `done` para `(project_id, timeline_revision, quality, platform)` → devuelve la URL cacheada, NO re-renderiza.
- **Persistencia**: **tabla propia `renders`** (decisión de Nico, no jsonb en jobs): `id, project_id, timeline_revision, quality, platform, status (queued|rendering|done|error), url, error, created_at` + índice por `(project_id, timeline_revision, quality, platform)`. Migración `0004_renders.sql` idempotente. `InMemoryRenderRepo` + `PgRenderRepo` (patrón M3/M5).
- **Pipeline**: fase `render` (deps `cta`, grafo = 11 fases) lanza la PREVIEW, espera (polling interno con timeout `RENDER_TIMEOUT_S`) y produce output `{render_id, url}`. **No muta la IR** (el render es consumidor, no editor; cero revisión nueva). El master NO es fase del grafo: se dispara explícitamente tras aprobación humana (CLI `vios render --master`, MCP en M13).

## 3. No funcionales
Reproducible (misma IR + mismos assets → mismo filtergraph, determinista; el plan se guarda junto al render para auditoría) · testeable sin ffmpeg (plan puro + `FfmpegRunner` inyectable con Fake; ffmpeg real solo en tests de contenedor, patrón M3/M4) · anti-alucinación (assets solo paths/URLs reales del storage; font de la ficha no disponible → ERROR con el nombre exacto, nunca sustituir en silencio) · un solo runtime Python (D5 se reinterpreta: la frontera Node desaparece porque desaparece Remotion — ADR D5 se actualiza con addendum, no se borra historia).

## 4. Diseño
- `vios_engine/render/`:
  - `plan.py` — `RenderPlan` (inputs ordenados, filter_complex como texto, maps, args encode, paths de sidecar .ass) + `ir_to_filtergraph(ir, asset_paths, quality, platform)` **pura**.
  - `subtitles.py` — track subtitle + params `subtitle_style` → archivo **ASS/SSA** (estilos con hex/font exactos; karaoke = un `Dialogue` con tags `\k` por palabra usando los clips por-palabra que ya deja M8). Puro: devuelve el contenido como string.
  - `masters.py` — `PLATFORM_MASTERS` (dato) + specs de preview.
  - `runner.py` — `FfmpegRunner` Protocol (`run(plan, out_path)`) + `SubprocessFfmpegRunner` real + `FakeFfmpegRunner` tests. Reutiliza el patrón Transcoder de M3.
  - `queue.py` — `RenderQueue`: asyncio.Semaphore(`RENDER_MAX_CONCURRENCY`) + contador por `client_id` + FIFO + idempotencia vía `RenderRepo`.
  - `repo.py` — `RenderRepo` Protocol + InMemory + Pg.
  - `service.py` — `RenderService.render(ir, quality, platform, client_id) -> RenderRecord` (orquesta: idempotencia → cola → plan → runner → repo) + `thumbnail(asset_path, frame, fps)`.
- **(d1) Ducking — decisión técnica a validar**: la IR ya trae `duck_ranges` PRECOMPUTADOS y auditados (Decision de M9). Dos opciones: **(A, propuesta)** filtro `volume` con expresiones `between(t,…)` sobre los duck_ranges → fiel 1:1 a la IR, determinista y auditable (lo que dice la Decision es lo que suena); **(B, tu mapping)** `sidechaincompress` → escucha la señal de voz en vivo (ignora los duck_ranges de la IR, resultado más "orgánico" pero no determinista ni trazable a la Decision). Propongo A como primaria por coherencia con el principio "la IR es la verdad", con B como plan estético si A suena robótica en el primer render real. En ambas, `loudnorm` al `target_lufs`. **Decides tú en la validación.**
- **Fases del render de una pieza** (interno, un solo comando ffmpeg cuando sea posible; si el filtergraph crece demasiado, pasos intermedios con archivos temp — decisión del plan, no del caller).
- `apps/render-svc/` se elimina del repo y del docker-compose (commit propio "chore: retira render-svc"); el puerto :4011 muere.
- Fuentes: `fonts/` del storage del cliente + `fontsdir` de libass / `fontfile` de drawtext.

## 5. Interfaces
`ir_to_filtergraph(ir, asset_paths, quality, platform) -> RenderPlan` · `RenderService.render(ir, quality, platform, client_id) -> RenderRecord` · `RenderService.thumbnail(asset_path, frame, fps) -> path` · `RenderRepo.find(project_id, revision, quality, platform)` / `.save(record)` · fase `render` como `PhaseHandler` estándar (output `{render_id, url}`, sin IR nueva).

## 6. Modelos de datos
Sin cambios en `vios_contracts` (la IR no se toca). Nuevos modelos SOLO en engine: `RenderPlan`, `RenderRecord` (espejo de la tabla `renders`). Migración `0004_renders.sql` con la tabla e índice de §2. Config nueva: `RENDER_MAX_CONCURRENCY`, `RENDER_MAX_PER_CLIENT`, `RENDER_TIMEOUT_S`.

## 7. Casos límite
Effect desconocido → error explícito · asset sin path en storage → error con el path exacto (nunca negro en silencio) · font de ficha ausente → error con nombre · timeline vacía → error "nada que renderizar" · duck_ranges vacíos → música a volumen constante + loudnorm · clip subtitle lleva texto en `source` (M8) → SIEMPRE vía .ass, jamás interpretado como path · render duplicado (misma revision/quality/platform) → URL cacheada, contador de cola intacto · cola llena de un cliente → sus jobs extra quedan `queued` sin bloquear a otros · ffmpeg exit≠0 → `status=error` con stderr recortado (reportar, no inventar; patrón M3) · timeout → kill del proceso + `error` · master pedido sin preview aprobada → permitido a nivel servicio pero la puerta de aprobación vive en el flujo (manual §2), anotado.

## 8. Riesgos
**(a)** Filtergraphs complejos (N clips × capas) pueden volverse ilegibles/frágiles → mitigación: `RenderPlan` construido por composición de bloques nombrados + golden tests de texto completo; si un grafo excede límites prácticos, el plan divide en pasos temp. **(b)** `zoompan` tiene fama de quisquilloso (fps/resolución) → aislarlo en un builder con tests propios; alternativa `scale`+`crop` con expresiones si falla en el smoke real. **(c)** Calidad visual de drawtext/ASS vs motion graphics React: suficiente para el MVP (cortes+subs+logo+zoom+música+CTA); motion graphics extremos se reevalúan post-MVP (YAGNI, trade-off aceptado por Nico). **(d)** Ducking A vs B (§4 d1) — decisión abierta para tu validación. **(e)** Tiempo de render en Docker sin GPU: preview 480p + concurrencia limitada; medir y anotar coste/tiempo real en BITACORA en el primer render (dato plan §8).

## 9. Tests
Puros sin ffmpeg (~18 engine): `ir_to_filtergraph` golden (3 IR M1 + rev-7 e2e → snapshot del filter_complex + inputs + args por quality/platform), effect desconocido → error, `subtitles.py` (líneas y karaoke `\k`, hex/font exactos, low_confidence), `PLATFORM_MASTERS` consumido por dato, `RenderQueue` (semáforo respeta techo, límite por cliente, FIFO/queued, idempotencia devuelve cache), `RenderService` con FakeRunner (happy, ffmpeg error, timeout), fase `render` (output correcto, IR intacta, job failed si el runner revienta tras retries), grafo 11 fases ordenado, golden e2e ampliado con fase render (Fake). Contracts: 0 nuevos (sin cambios de contrato). Reales (skip en CI, contenedor): render preview de la IR golden e2e → mp4 verificado con ffprobe (duración≈900f/30fps, 480p, streams v+a) + thumbnail JPEG + un master IG.

## 10. Plan implementación
1) Exportar fixture IR rev-7 del e2e a golden → 2) `masters.py` + `subtitles.py` (TDD puro) → 3) `plan.py` `ir_to_filtergraph` (TDD golden, effect a effect en el orden M8→M10) → 4) `repo.py` + migración 0004 → 5) `queue.py` (TDD concurrencia/idempotencia) → 6) `runner.py` + `service.py` (TDD con Fake) → 7) fase `render` + grafo 11 + golden e2e → 8) retirar `apps/render-svc` + compose → 9) smoke real en contenedor (preview + thumbnail + master; TÚ ves la preview = validación humana) → 10) ruff/tests/doc cierre/BITACORA/commit+push.

## 11. Docs/pendientes
- **(d1) Ducking A (volume por duck_ranges, fiel a la IR) vs B (sidechaincompress)** — tu llamada en la validación de este doc.
- ADR D5 addendum: "render Node/Remotion → FFmpeg nativo en Python (2026-07-17, directiva Nico: cero atadura de licencias de terceros)".
- Transiciones entre clips → contrato nuevo post-MVP (el render no las inventa).
- .srt export (subtítulos como archivo aparte) → M14 si publishing lo pide; v1 burn-in.

## 12. Cierre (como quedó implementado — 2026-07-17, tras aprobación del v2)
- `vios_engine/render/`: `plan.py` (`ir_to_filtergraph` pura + `RenderPlan`), `subtitles.py` (ASS con karaoke `\k`, hex/font exactos), `masters.py` (`PLATFORM_MASTERS` + constantes ducking/logo/CTA), `queue.py` (semáforo global + por cliente), `runner.py` (Subprocess + Fake, stderr reportado, timeout con kill), `repo.py` (InMemory + Pg, id = clave de idempotencia), `service.py`. Migración `0004_renders.sql` con índice único por (project, revision, quality, platform).
- Ducking opción A implementado con rampas: `volume='V*(if(between(t,s,s+0.15),rampa_in,if(...,0.3,if(...,rampa_out,1))))'` + `loudnorm` — determinista, fiel a los duck_ranges de la Decision M9.
- Goldens de filtergraph: 4 (3 IR M1 + `reel_f4_rev7.json` nuevo en contracts/golden, generado por `tests/make_golden_rev7.py`); regenerables con `tests/make_filtergraph_goldens.py` solo tras cambio deliberado del plan.
- Grafo 11 fases (`…→cta→render`); la fase render produce `{render_id, url}` sin revisión nueva (IR intacta, verificado en golden e2e).
- `apps/render-svc` ELIMINADO (repo + compose + config `render_port`); config nueva: `render_max_concurrency`/`render_max_per_client`/`render_timeout_s`. Dockerfile engine ahora copia `playbooks/` (arregla 7 tests de loaders que ya fallaban en contenedor).
- 2 bugs cazados por el smoke REAL (justifica la puerta): (1) `scale=ih*1.7778` truncaba 1919.99→1919 y el crop 1920 no cabía → `ceil()` en la expresión; (2) el input del logo con `-loop 1` sin `-t` era infinito y ffmpeg no terminaba → `-t` acotado al fin del overlay.
- Coste medido (dato plan §8): preview 480p de una pieza de 30s ≈ **25 s** de ffmpeg en el contenedor (M2 vía Docker); suite completa contenedor 33 s.
- Tests: engine 106→127 local (+2 smokes reales en contenedor = 129) · contracts 50 · ruff limpio.
- Pendiente para la puerta humana: primer render con BRUTO REAL de cliente (los smokes usan lavfi) — es el hito MVP tras M12.
