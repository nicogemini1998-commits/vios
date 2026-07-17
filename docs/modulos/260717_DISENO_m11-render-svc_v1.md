# M11 · F5 Render + QA — Render Service (IR → Remotion → preview/masters) (v1)

> VIOS · 2026-07-17 · KAREN (Fable 5) · Estado: **SUSTITUIDO por `260717_DISENO_m11-render-ffmpeg_v2.md`** — Nico rechazó Remotion (licencia comercial de terceros = atadura) y ordenó render FFmpeg nativo en Python, eliminando render-svc. La arquitectura data-driven de este v1 sí fue aprobada y se conserva en v2.

## 1. Objetivo
Primer módulo de F5 y camino directo al hito MVP: convertir la Timeline IR (revisión 7, 6 capas F4) en vídeo real. `apps/render-svc` (Node 20 + Remotion, host :4011) recibe una IR + acceso a los assets y produce **preview 480p barata** primero y **masters por plataforma** solo tras aprobación (2 puertas del manual). El engine Python lo consume vía HTTP con cliente inyectable (testeable sin Remotion, D5: frontera por servicios).

## 2. Requisitos funcionales
- **API render-svc**: `POST /render` `{ir, quality: "preview"|"master", platform}` → `{render_id}` (asíncrono, render tarda); `GET /render/{id}` → `{status: queued|rendering|done|error, output_url, error}`; `GET /health` (ya existe). Cola con concurrencia 1 en v1 (plan §7: previews baratas, masters solo tras aprobación).
- **Intérprete genérico de IR** (decisión clave, ver §4): UNA composición Remotion data-driven (`TimelineComposition`) que interpreta la IR JSON directamente — no se genera código por proyecto ni composición por playbook. La IR ya es frame-based con fps en raíz: mapping 1:1 a Remotion (que también es frame-based), cero aritmética de tiempo nueva.
- **Mapping del catálogo de effects (los 5, cerrado en M8–M10)**: `subtitle_style` → texto estilado con hex/font exactos de params; `logo_overlay` → `<Img>` en esquina con margin_rel; `zoom` → `interpolate` de scale entre scale_from/scale_to a lo largo del clip; `music_mix` → `<Audio>` con volume_rel + rampas en duck_ranges; `cta_overlay` → overlay de texto con font/color de params. Effect desconocido → error explícito (catálogo cerrado, no se ignora en silencio).
- **Tracks**: orden del array = orden de apilado (posteriores encima); `video`/`audio`/`subtitle`/`graphic` → capas Remotion; `Transform` (scale/x/y/rotation/opacity) → style transform del clip.
- **Preview**: 480p (misma lógica scale=-2:480 que el proxy M3), codec rápido. **Master**: resolución del canvas, encode final FFmpeg por plataforma (h264 + AAC v1).
- **Thumbnail**: endpoint `POST /thumbnail` `{asset_url, frame, fps}` → JPEG del frame del marker `thumbnail` de M10 (extracción ffmpeg, no Remotion — es un frame del SOURCE).
- **Engine (lado Python)**: interfaz `RenderClient` inyectable (HTTPRenderClient real + FakeRenderClient tests) + fase `render` en el grafo (deps `cta`, 11 fases) que lanza preview, hace polling y guarda `render_id`/`output_url` en el output de fase. El render NO muta la IR (no hay revisión nueva; es consumidor, no editor).

## 3. No funcionales
Render reproducible (misma IR → mismo vídeo); testeable sin Remotion/ffmpeg (interfaces inyectables en Python; en Node el mapping IR→props es función pura testeable con `node --test`); anti-alucinación (assets solo por URL/paths reales, fuentes de la ficha — si una font no está disponible, ERROR explícito, nunca sustituir en silencio); MotionKit hard rules en las composiciones (solo transform/opacity animados, nada de layout thrashing — mitigación plan §7 "calidad template IA").

## 4. Diseño
- **Intérprete genérico vs composición por playbook**: elijo intérprete genérico. La IR ya ES la descripción completa de la pieza (D1: agentes razonan sobre datos, render los ejecuta); una composición por playbook duplicaría lógica de edición en JS y rompería D1. El playbook influye en la IR, no en el render.
- **render-svc**: `src/index.js` (HTTP + cola en memoria v1) · `src/ir-to-props.js` (validación contra `timeline_ir.schema.json` exportado por contracts + normalización a props: función PURA, el corazón testeable) · `src/TimelineComposition.jsx` (interpreta props) · `src/effects/` (un componente por effect del catálogo) · `src/encode.js` (FFmpeg preview/master/thumbnail).
- **Acceso a assets**: v1 volumen compartido en docker-compose (engine y render-svc montan el mismo storage local de M3); las URLs http(s) (Supabase futuro, M3.1) se descargan a tmp antes de renderizar. El render-svc NO conoce Supabase (D6 queda en el engine).
- **Engine**: `vios_engine/render/client.py` (`RenderClient` Protocol + `HTTPRenderClient` httpx + `FakeRenderClient`); fase `render` con `max_attempts=2` y polling con timeout de config (`RENDER_TIMEOUT_S`).
- **Fuentes del cliente**: carpeta `fonts/` montada + `@font-face` por ficha; font no disponible → error del job con nombre exacto (NEEDS_INPUT de facto).

## 5. Interfaces
`POST /render` / `GET /render/{id}` / `POST /thumbnail` (HTTP, JSON) · `RenderClient.render(ir, quality, platform) -> render_id` · `RenderClient.status(render_id) -> RenderStatus` · fase `render` como `PhaseHandler` estándar (no produce IR, produce output `{render_id, output_url}`).

## 6. Modelos de datos
**Sin cambios en contratos Python.** El JSON Schema versionado (`timeline_ir.schema.json`) pasa a ser consumido por Node (RF8 cumplida: era su propósito). Nuevo modelo solo en engine (no contrato compartido): `RenderStatus` pydantic en `render/client.py`. Migración `0004`: columna `renders jsonb` en `jobs` (o tabla `renders`) — decidir contigo: v1 propongo columna jsonb (YAGNI hasta publishing M14).

## 7. Casos límite
IR con effect fuera del catálogo → error explícito · asset inexistente en storage → error con path exacto (no se renderiza negro en silencio) · font de la ficha no instalada → error con nombre · timeline vacía → error "nada que renderizar" · duck_ranges vacíos → música a volumen constante · clip subtitle con texto como `source` (así lo dejó M8) → el intérprete lo trata como texto, nunca como path · render-svc caído → fase `render` falla con mensaje claro tras retries (el job queda `failed`, la IR y checkpoints intactos) · preview OK pero master falla → estados independientes por render_id.

## 8. Riesgos
**(a) Mapping IR→Remotion torcido = refactor caro** (motivo de esta validación previa): mitigación — `ir-to-props.js` puro con golden tests contra las 3 IR golden de M1 + la IR del golden e2e (revisión 7, exportada como fixture) ANTES de tocar JSX. **(b) Remotion como dependencia externa** (licencia: Cliender ya la usa en CDPro :4010 — confirmar que cubre este segundo servicio; instalación pesada): regla acordada — si falta la pieza, stub + test + nota en BITACORA y seguir. **(c) Reproducibilidad de fonts/antialiasing entre máquinas: aceptable v1, el QA humano mira la preview. **(d) Render lento en Docker sin GPU: previews 480p + cola concurrencia 1; medir en el primer render real y anotar coste/tiempo en BITACORA (dato para plan §8). **(e) v1 sin transiciones entre clips (la IR no las modela aún): cortes secos — coherente con lo que producen los agentes; transiciones = contrato nuevo futuro, no las inventa el render.

## 9. Tests
Node (`node --test`, sin render real): `ir-to-props` valida contra schema y rechaza effect desconocido; mapping de las 3 IR golden M1 + fixture e2e (tracks/clips/effects/markers → props esperados, snapshot JSON); rampas de ducking calculadas. Python engine (~8): FakeRenderClient — fase `render` feliz (output con render_id/url), polling con timeout, render-svc caído → failed tras retries, IR intacta (sin revisión nueva), grafo 11 fases ordenado, golden e2e con fase render añadida. Reales (skip en CI, como ffmpeg/ML): 1 render preview de la IR golden e2e en contenedor + thumbnail ffmpeg.

## 10. Plan implementación
1) Exportar fixture IR del golden e2e (rev 7) a `packages/contracts/tests/golden/` → 2) `ir-to-props.js` + tests Node (puro, sin Remotion) → 3) TimelineComposition + 5 componentes de effects → 4) cola + endpoints + encode FFmpeg → 5) `RenderClient` Python + fase `render` (TDD con Fake) → 6) docker-compose (volumen assets compartido, imagen Node con ffmpeg) → 7) render real de la golden IR (verificación humana: TÚ miras la preview) → 8) ruff/tests/doc/BITACORA/commit+push.

## 11. Docs/pendientes
- Confirmar contigo: ¿la licencia Remotion de CDPro cubre este servicio? · ¿columna `renders jsonb` o tabla propia? · masters por plataforma: ¿specs exactas (bitrate/codec) por red o defaults sensatos v1?
- Transiciones entre clips → contrato nuevo (post-MVP, no en M11).
- Burn-in vs subtítulos como archivo .srt aparte → v1 burn-in (es el estilo reel); .srt export en M14 si publishing lo pide.

## 12. Cierre
_(se rellena al cerrar el módulo)_
