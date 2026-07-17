# DISEÑO M3 — Media Pipeline (F2 Ingesta)

> **Módulo:** M3 · **Fase:** F2 (Ingesta) · **Versión:** v1 · **Fecha:** 2026-07-16
> **Autor:** KAREN (Opus 4.8) · **Plan padre:** `260716_PLAN_video-intel-os_v1.md` (§F2, D4, D6)
> **Estado:** DISEÑO + IMPLEMENTACIÓN (confianza de Nico)

---

## 1. Objetivo

Construir la tubería de ingesta de material bruto: **upload → Storage → proxies (FFmpeg) → hash cache**. Deja cada asset almacenado (por URL, nunca base64), con proxy de baja resolución para trabajo rápido, audio extraído para M4 (Whisper), metadata técnica (duración, resolución, fps, audio) y **deduplicado por hash** — mismo bruto no se re-almacena ni se re-analizará (D4: analizar una vez, editar N veces).

**No incluye:** el análisis inteligente (transcript/escenas/energía = M4), ni agentes. M3 deja el asset *listo para analizar*.

---

## 2. Requisitos funcionales

- **RF1** — `ingest_media(project_id, source, ...)`: sube el original, genera proxy 480p, extrae audio, calcula metadata, persiste un `AssetRecord`.
- **RF2** — **Hash-cache (D4):** hash SHA-256 del contenido. Si ya existe un asset con ese hash → se reutiliza (no re-almacena ni re-transcodifica), se devuelve marcado `cached=True`.
- **RF3** — **Storage por URL (D6):** el original y el proxy se guardan en un backend de almacenamiento y se referencian por URL/clave. **Nunca base64 en DB** (lección CDPro).
- **RF4** — Proxy H.264 480p (trabajo/preview rápido) + extracción de audio (WAV/AAC) para M4.
- **RF5** — Metadata técnica vía ffprobe: `duration_s, width, height, fps, has_audio, codec, size_bytes, mime`.
- **RF6** — Casos límite reportados, no adivinados (manual §2): vídeo sin audio, archivo corrupto, formato no soportado → `status="error"` + motivo, nunca invención.
- **RF7** — Todo desacoplado por interfaces (Storage/Prober/Transcoder/Repo) → testeable sin FFmpeg ni Supabase.
- **RF8** — Migración `0002` que extiende la tabla `assets` con las columnas de proxy/metadata/estado.

## 3. Requisitos no funcionales

- **RNF1 · FFmpeg vive en el contenedor.** Imagen `engine` añade `ffmpeg`. En local sin ffmpeg, la lógica se prueba con fakes; los tests que tocan ffmpeg real se marcan `skip` si no está.
- **RNF2 · Idempotencia.** Re-ingerir el mismo archivo no duplica (RF2) ni deja basura en Storage.
- **RNF3 · Sin secretos en código.** Credenciales Supabase Storage vía `.env` (ya en config M0).
- **RNF4 · Storage intercambiable.** `LocalStorage` (dev/tests, filesystem) y `SupabaseStorage` (producción) tras la misma interfaz. Cambiar uno no toca la pipeline.
- **RNF5 · Coste.** M3 no invoca LLM. FFmpeg y hashing son deterministas y baratos.

---

## 4. Diseño

### 4.1 Interfaces (puertos) e implementaciones
```
StorageBackend  (protocolo)   put(local_path, key)->url · open(key) · exists(key) · url_for(key)
  ├── LocalStorage            filesystem bajo media_root; url = file:///... o /media/<key>
  └── SupabaseStorage         bucket Supabase (producción) — impl fina sobre supabase-py (M3: interfaz + stub, real cuando exista el proyecto)

MediaProber     (protocolo)   probe(path)->MediaMeta
  └── FfprobeProber           parsea `ffprobe -show_format -show_streams -of json`

Transcoder      (protocolo)   make_proxy(src,dst,height) · extract_audio(src,dst)
  └── FfmpegTranscoder        `ffmpeg -i ... -vf scale=-2:480 -c:v libx264 ...` / `-vn -acodec ...`

AssetRepo       (protocolo)   find_by_hash(hash) · add(record) · get(id)
  ├── InMemoryAssetRepo       tests
  └── PgAssetRepo             asyncpg sobre tabla `assets` (real)
```
La pipeline recibe estas 4 dependencias inyectadas → unidad testeable con fakes, producción con impls reales.

### 4.2 Flujo `ingest_media`
```
1. hash = sha256(source)
2. cached = repo.find_by_hash(hash);  si existe → return (cached=True)   # D4
3. key = f"{hash}/original{ext}"; original_url = storage.put(source, key)
4. meta = prober.probe(source)                                          # duracion, wxh, fps, audio
5. proxy: transcoder.make_proxy → storage.put(f"{hash}/proxy_480.mp4")
6. audio (si meta.has_audio): transcoder.extract_audio → storage.put(f"{hash}/audio.wav")
7. record = AssetRecord(id, project_id, hash, original_url, proxy_url, audio_url, meta..., status="ready")
8. repo.add(record); return (record, cached=False)
```
Errores en 3-6 → `status="error"`, `error` con motivo, se persiste igual para trazabilidad (RF6).

### 4.3 Modelos (engine, no contrato cross-service aún)
- `MediaMeta { duration_s, width, height, fps, has_audio, codec, size_bytes, mime }`
- `AssetRecord { id, project_id, hash, original_url, proxy_url, audio_url|None, meta: MediaMeta, status, error|"" }`
`AssetRecord` es metadata de almacenamiento; `MediaIntelligence` (M4) es el análisis — separados a propósito.

### 4.4 Código
```
apps/engine/src/vios_engine/media/
  models.py       AssetRecord, MediaMeta
  hashing.py      sha256_file
  storage.py      StorageBackend + LocalStorage + SupabaseStorage(stub)
  probe.py        MediaProber + FfprobeProber
  transcode.py    Transcoder + FfmpegTranscoder
  repo.py         AssetRepo + InMemoryAssetRepo
  pipeline.py     ingest_media(...)
```
Migración `db/migrations/0002_assets_media.sql`.

---

## 5. Interfaces (API pública)
```python
ingest_media(project_id, source, *, storage, prober, transcoder, repo,
             proxy_height=480) -> IngestResult      # {record: AssetRecord, cached: bool}
LocalStorage(root) · FfprobeProber() · FfmpegTranscoder() · InMemoryAssetRepo()
sha256_file(path) -> str
```

## 6. Modelos de datos

Migración `0002` sobre `assets` (M0 tenía: id, project_id, storage_url, hash, created_at):
```
ALTER TABLE assets ADD COLUMN proxy_url text;
ALTER TABLE assets ADD COLUMN audio_url text;
ALTER TABLE assets ADD COLUMN mime text;
ALTER TABLE assets ADD COLUMN size_bytes bigint;
ALTER TABLE assets ADD COLUMN width int;
ALTER TABLE assets ADD COLUMN height int;
ALTER TABLE assets ADD COLUMN duration_s double precision;
ALTER TABLE assets ADD COLUMN fps double precision;
ALTER TABLE assets ADD COLUMN has_audio boolean;
ALTER TABLE assets ADD COLUMN status text DEFAULT 'ready';
ALTER TABLE assets ADD COLUMN error text;
CREATE INDEX IF NOT EXISTS idx_assets_hash ON assets(hash);
```
`storage_url` de M0 = `original_url`. Idempotente donde se pueda (`ADD COLUMN IF NOT EXISTS` en PG16).

## 7. Casos límite

- **CL1** — Mismo archivo ingerido 2 veces → 2ª vez `cached=True`, sin nuevo almacenamiento (RF2).
- **CL2** — Vídeo sin pista de audio → `has_audio=False`, no se extrae audio, no error.
- **CL3** — Archivo corrupto / no media → ffprobe falla → `status="error"`, motivo; no se inventan metadatos.
- **CL4** — Formato raro (mov, mkv, webm) → se acepta (FFmpeg lo soporta); proxy siempre mp4/H.264.
- **CL5** — Vertical vs horizontal → se conserva aspect en el proxy (`scale=-2:480` mantiene ratio).
- **CL6** — Source es URL remota → M3 v1 asume ruta local ya descargada; descarga remota = follow-up (documentado, no silencioso).

## 8. Riesgos

| Riesgo | Prob. | Mitigación |
|---|---|---|
| FFmpeg ausente en dev bloquea tests | Alta | Interfaces + fakes; ffmpeg real solo en Docker; tests reales `skip` si falta |
| Storage Supabase aún no existe | Media | Interfaz + LocalStorage funcional ya; SupabaseStorage se completa al crear el proyecto (M3.1) |
| Proxies llenan disco | Media | 480p; limpieza por hash; cache evita duplicados |
| ffprobe parsing frágil | Media | Parsear JSON de ffprobe (no regex); defaults seguros + test con salida fija |

## 9. Tests (TDD, con fakes)

- **T1** — `ingest_media` con FakeStorage/FakeProber/FakeTranscoder/InMemoryRepo → `AssetRecord` con original_url, proxy_url, audio_url, status="ready".
- **T2** — Re-ingesta del mismo contenido → `cached=True`, repo no crece (CL1).
- **T3** — Prober reporta `has_audio=False` → no se llama a `extract_audio`, `audio_url is None` (CL2).
- **T4** — Prober lanza (archivo corrupto) → `status="error"`, motivo presente, sin metadata inventada (CL3).
- **T5** — `sha256_file` estable y distinto para contenidos distintos.
- **T6** — `LocalStorage.put` copia y `url_for` devuelve clave estable; `exists` correcto.
- **T7** — `InMemoryAssetRepo.find_by_hash` encuentra/whiffs correctamente.
- **T8 (skip si no ffmpeg)** — `FfprobeProber`/`FfmpegTranscoder` sobre un clip real de 1 s generado con ffmpeg: proxy existe y `probe` da duración ≈1 s.

Cobertura objetivo M3 (lógica pipeline+storage+repo, excl. impls ffmpeg): **≥85%**.

## 10. Plan de implementación

1. Tests T1–T7 (rojos) con fakes.
2. `models.py`, `hashing.py`.
3. `storage.py` (LocalStorage), `repo.py` (InMemory).
4. `probe.py`/`transcode.py`: protocolos + impls ffmpeg (parseo JSON de ffprobe).
5. `pipeline.py` `ingest_media`.
6. Migración `0002` + añadir `ffmpeg` al Dockerfile engine.
7. Verde + ruff + cobertura; T8 con ffmpeg si disponible (aquí `skip`).
8. Cierre: doc, BITACORA, memoria, commit.

## 11. Documentación / cierre

- Este doc en `01. MODULOS/`.
- Nota en README repo: `ffmpeg` requerido para ingesta real (contenedor lo trae; local `brew install ffmpeg`).
- BITACORA M3; memoria; commit.

---

## Salida esperada M3 (criterio de cierre)

✅ `ingest_media` con hash-cache (D4) y storage por URL (D6) · ✅ interfaces Storage/Prober/Transcoder/Repo + impls Local/FFmpeg/InMemory · ✅ migración 0002 + ffmpeg en imagen · ✅ tests T1–T7 verdes (T8 skip sin ffmpeg), cobertura ≥85% · → siguiente **M4 · MediaIntelligence** (Whisper word-level + PySceneDetect + librosa sobre el proxy/audio que deja M3).
