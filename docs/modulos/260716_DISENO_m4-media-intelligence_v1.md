# DISEÑO M4 — MediaIntelligence (F2 Ingesta, cierra F2)

> **Módulo:** M4 · **Fase:** F2 · **Versión:** v1 · **Fecha:** 2026-07-16
> **Autor:** KAREN (Opus 4.8) · **Plan padre:** `260716_PLAN_video-intel-os_v1.md` (§F2, D3, D4)
> **Estado:** DISEÑO + IMPLEMENTACIÓN (confianza de Nico)

---

## 1. Objetivo

Convertir un asset ingerido (M3) en un **`MediaIntelligence`** cacheado por hash: transcript word-level (Whisper), escenas (PySceneDetect), energía y silencios de audio (librosa), keyframes por escena y score de calidad. Es el análisis CARO que, gracias al cache (D4), se hace **una vez por bruto** y alimenta N ediciones/formatos sin re-analizar. Todo el trabajo de M4 es **determinista o modelo local** (D3: workers baratos y reproducibles); **cero LLM** en el núcleo (la visión con Claude es opcional e inyectable).

**No incluye:** decisiones de edición (Director/Story = F3), ni subtítulos estilados (Subtitle Agent = F4). M4 solo produce el conocimiento verificable del material.

---

## 2. Requisitos funcionales

- **RF1** — `analyze_asset(asset, ...)` → `MediaIntelligence` con: `transcript`, `scenes`, `silences`, `energy`, `keyframes`, `quality`, `duration_s`, `fps`.
- **RF2** — **Transcript word-level** (Whisper): segmentos con palabras y timestamps + probabilidad. Marca `low_confidence` cuando la prob media es baja → base de `[inaudible]` (manual §2.3), nunca se inventa texto.
- **RF3** — **Escenas** (PySceneDetect): lista de cortes `{index, start_s, end_s}`.
- **RF4** — **Audio** (librosa): curva de energía (RMS muestreada) + tramos de silencio `{start_s, end_s}` (valles de retención para B-Roll en F4).
- **RF5** — **Keyframes**: 1 por escena (punto medio) como timestamps deterministas. Descripción de frame = opcional vía `VisionAnalyzer` inyectable (Claude); por defecto vacía (coste 0).
- **RF6** — **Quality score**: `{overall, audio_ok, notes[]}` heurístico (p.ej. audio ausente, muchos silencios, resolución baja). Señales, no veredictos absolutos.
- **RF7** — **Cache por hash (D4):** `IntelligenceCache.get(hash)` antes de analizar; si existe → se devuelve, no se recomputa.
- **RF8** — **Unidades = segundos** (dominio de análisis, relativo al source). La conversión a frames la hace el Edit Agent con `fps` (frontera con Timeline IR documentada).
- **RF9** — Desacople por interfaces (Transcriber/SceneDetector/AudioAnalyzer/FrameSampler/VisionAnalyzer/Cache) → testeable sin modelos ni ffmpeg.

## 3. Requisitos no funcionales

- **RNF1 · Dependencias pesadas opcionales.** `faster-whisper`, `scenedetect`, `librosa` en extra `[analysis]`, no en deps base (engine ligero). Impls con import perezoso + error claro si faltan.
- **RNF2 · Determinista/reproducible (D3).** Mismo asset → mismo MediaIntelligence (salvo no-determinismo del modelo Whisper, acotado con `beam_size` fijo). Sin LLM en el core.
- **RNF3 · Caro se cachea (D4).** El análisis solo corre en cache-miss. Cache keyed por `source_hash`.
- **RNF4 · GPU opcional.** faster-whisper usa CPU por defecto (`compute_type=int8`); GPU si está disponible. Config vía `.env` (`WHISPER_MODEL`, `WHISPER_DEVICE`).
- **RNF5 · Anti-alucinación.** Transcript = salida literal de Whisper. Tramos ininteligibles → `low_confidence`, jamás texto inventado (manual §2.1/§2.3).

---

## 4. Diseño

### 4.1 Contrato `MediaIntelligence` (sustituye stub M0, en `packages/contracts`)
```
MediaIntelligence
├── schema_version, asset_id, source_hash
├── duration_s, fps
├── transcript: Transcript { language, segments:[Segment{start_s,end_s,text,low_confidence,words:[Word{start_s,end_s,text,prob}]}] }
├── scenes:    [Scene{index, start_s, end_s}]
├── silences:  [Silence{start_s, end_s}]
├── energy:    [EnergyPoint{at_s, rms}]
├── keyframes: [Keyframe{at_s, scene_index, description}]     # description opcional (vision)
└── quality:   QualityScore{ overall: float, audio_ok: bool, notes: [str] }
```

### 4.2 Interfaces (puertos) e impls
```
Transcriber      transcribe(audio_path, language?) -> Transcript
  └── WhisperTranscriber      faster-whisper (word_timestamps=True), lazy import

SceneDetector    detect(video_path) -> list[Scene]
  └── PySceneDetectDetector   ContentDetector, lazy import

AudioAnalyzer    analyze(audio_path) -> (energy: list[EnergyPoint], silences: list[Silence])
  └── LibrosaAudioAnalyzer    RMS + split por umbral dB, lazy import

FrameSampler     sample(scenes, duration_s) -> list[Keyframe]     # determinista, 1/escena (punto medio)
  └── MidpointFrameSampler    puro (sin deps)

VisionAnalyzer   describe(video_path, keyframes) -> list[Keyframe]  # OPCIONAL (Claude); None = sin descripción
IntelligenceCache get(hash)->MI|None · put(hash, mi)
  └── InMemoryIntelligenceCache (tests) · (Pg/Storage en M4.1)
```

### 4.3 Flujo `analyze_asset`
```
1. hit = cache.get(asset.hash);  si existe → return hit                    # D4
2. transcript = transcriber.transcribe(asset.audio_url) si asset.meta.has_audio, si no vacío
3. scenes = scene_detector.detect(asset.proxy_url|original)
4. energy, silences = audio_analyzer.analyze(asset.audio_url) si has_audio
5. keyframes = frame_sampler.sample(scenes, duration_s)
6. keyframes = vision.describe(...) si vision inyectado (opcional)
7. quality = score(meta, transcript, silences)                            # heuristico
8. mi = MediaIntelligence(...); cache.put(asset.hash, mi); return mi
```
Cada paso que falla (modelo/archivo) → se registra en `quality.notes` y se continúa con lo disponible; nunca se inventa (RF/RNF5).

### 4.4 Código
```
apps/engine/src/vios_engine/intelligence/
  analyzer.py    interfaces + analyze_asset + score()
  transcribe.py  WhisperTranscriber (lazy)
  scenes.py      PySceneDetectDetector (lazy)
  audio.py       LibrosaAudioAnalyzer (lazy)
  sampler.py     MidpointFrameSampler (puro)
  cache.py       InMemoryIntelligenceCache
```
Contrato real en `packages/contracts/media_intelligence.py`.

---

## 5. Interfaces (API pública)
```python
analyze_asset(asset, *, transcriber, scene_detector, audio_analyzer,
              frame_sampler, cache, vision=None) -> MediaIntelligence
MidpointFrameSampler() · InMemoryIntelligenceCache()
WhisperTranscriber(model, device) · PySceneDetectDetector() · LibrosaAudioAnalyzer()
# contracts
MediaIntelligence, Transcript, Segment, Word, Scene, Silence, EnergyPoint, Keyframe, QualityScore
```

## 6. Modelos de datos

Ver §4.1. Persistencia (M4.1): `MediaIntelligence` → JSON en Storage o columna `assets.intelligence jsonb`, keyed por hash. En M4 solo cache en memoria + contrato serializable (Pydantic `model_dump_json`).

## 7. Casos límite

- **CL1** — Cache hit → no recomputa (D4).
- **CL2** — Vídeo sin audio → transcript vacío, energy/silences vacíos, `quality.audio_ok=False`, nota. No error.
- **CL3** — Audio sucio / tramo ininteligible → segmento `low_confidence=True`; el texto de Whisper se conserva tal cual, el consumidor decide `[inaudible]`.
- **CL4** — Vídeo sin cortes (plano único) → 1 escena que cubre toda la duración.
- **CL5** — Modelo/lib ausente → error claro "instala extra [analysis]"; tests con fakes no lo tocan.
- **CL6** — Vertical vs horizontal → indiferente para transcript/escenas/audio; keyframes usan timestamps, no píxeles.

## 8. Riesgos

| Riesgo | Prob. | Mitigación |
|---|---|---|
| Whisper pesado/lento sin GPU | Alta | Modelo configurable (`small`/`medium`/`large-v3`), `int8` CPU, cache agresivo (D4) |
| No-determinismo de Whisper | Media | `beam_size` fijo; se acepta variación menor; el test real compara estructura, no texto exacto |
| Deps ML rompen build engine | Media | Extra `[analysis]` separado; core engine no las importa; impls lazy |
| Inventar texto en tramos malos | — | `low_confidence` + conservar literal; prohibido parafrasear (RNF5) |

## 9. Tests (TDD, con fakes)

- **T1** — `analyze_asset` con fakes → MI con transcript/scenes/silences/energy/keyframes/quality poblados.
- **T2** — Cache hit: segundo `analyze_asset` no llama a los analizadores (D4).
- **T3** — Asset sin audio → transcript vacío, `quality.audio_ok=False`, no llama transcriber/audio (CL2).
- **T4** — `MidpointFrameSampler`: 1 keyframe por escena, en el punto medio, `scene_index` correcto.
- **T5** — `score()` heurístico: sin audio → audio_ok False + nota; muchos silencios → nota.
- **T6** — Segmento con prob baja → `low_confidence=True` (marcado, texto intacto) (CL3).
- **T7** — MediaIntelligence round-trip JSON (`model_dump_json`/`model_validate_json`).
- **T8 (skip si faltan libs/ffmpeg)** — WhisperTranscriber/PySceneDetect/librosa sobre el clip real de 1 s de M3: transcript no vacío o language detectado, ≥1 escena.

Cobertura objetivo M4 (orquestación + sampler + score + cache + contrato, excl. impls ML): **≥85%**.

## 10. Plan de implementación

1. Contrato `media_intelligence.py` real + tests T7.
2. Tests T1–T6 (rojos) con fakes.
3. `analyzer.py` (interfaces + `analyze_asset` + `score`), `sampler.py`, `cache.py`.
4. Impls lazy: `transcribe.py`, `scenes.py`, `audio.py` + extra `[analysis]` en pyproject.
5. Verde + ruff + cobertura; T8 skip local.
6. Cierre: doc, BITACORA, memoria, commit. **F2 cerrada.**

## 11. Documentación / cierre

- Este doc en `01. MODULOS/`.
- README repo: extra `[analysis]` + `WHISPER_MODEL`/`WHISPER_DEVICE` en `.env`.
- BITACORA M4 (cierre F2); memoria; commit.

---

## Salida esperada M4 (criterio de cierre)

✅ Contrato `MediaIntelligence` real + serializable · ✅ `analyze_asset` con cache por hash (D4) e interfaces inyectables · ✅ transcript word-level con `low_confidence` (anti-alucinación) · ✅ escenas/silencios/energía/keyframes/quality · ✅ tests T1–T7 verdes (T8 skip sin libs), cobertura ≥85% · → **F2 (Ingesta) cerrada** → siguiente F3 (Cerebro: M5 Pipeline Engine, M6 Director+Story, M7 Edit).
