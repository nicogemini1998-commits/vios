# DISEÑO M2 — ClientProfile + Playbook (F1 Contratos)

> **Módulo:** M2 · **Fase:** F1 (cierra Contratos) · **Versión:** v1 · **Fecha:** 2026-07-16
> **Autor:** KAREN (Opus 4.8) · **Plan padre:** `260716_PLAN_video-intel-os_v1.md` (D7)
> **Contrato hermano:** `260716_MANUAL_uso-vios_v1.md` §5 (ficha cliente A–H) + §2 (anti-alucinación)
> **Estado:** DISEÑO + IMPLEMENTACIÓN (confianza de Nico para avanzar)

---

## 1. Objetivo

Implementar los dos contratos que faltan de F1: **ClientProfile** (la ficha de conocimiento del cliente, bloques A–H del manual) y **Playbook** (estilo/estrategia de edición como dato, D7). Incluye: schemas Pydantic reales (sustituyen los stubs de M0), loader YAML, **gate de completitud** (sin bloques A–F → VIOS no edita, base de la regla anti-alucinación §5 del manual), 2 playbooks semilla y 1 cliente semilla con **branding real Cliender verificado**.

**No incluye:** persistencia Supabase (llega en F2/M3), ni la lógica de agentes que consume estos contratos (F3+).

---

## 2. Requisitos funcionales

- **RF1** — `ClientProfile` modela los 8 bloques del manual: A Identidad · B Identidad visual · C Voz/tono · D Audiencia/objetivo · E Reglas de edición · F Biblioteca · G Comercial · H Métricas.
- **RF2** — Bloques A–F son **obligatorios**; G–H opcionales (H se rellena con el uso). El tipo permite perfiles incompletos (para poder reportarlos); la completitud se valida por función, no por construcción.
- **RF3** — `client_missing_blocks(profile) -> list[str]`: lista bloques A–F ausentes o con campos críticos vacíos. `is_client_editable(profile) -> bool` = lista vacía.
- **RF4** — `Playbook` modela: beats (con duración relativa que suma ≈1.0), hook spec, política de subtítulos/música/ritmo, CTA, duración ideal por plataforma, métricas objetivo (D7, plan §4).
- **RF5** — `validate_playbook(pb)`: beats suman ≈1.0 (±0.01), duraciones min≤max, `hook.max_seconds>0`, rel_duration>0.
- **RF6** — Loader YAML: `load_client(path)`, `load_playbook(path)`, `load_clients_dir(dir)`, `load_playbooks_dir(dir)` → modelos validados; error claro si el YAML no cumple.
- **RF7** — 2 playbooks semilla: **reel-educativo** y **podcast-clips** (los del plan §F1).
- **RF8** — 1 cliente semilla: **Cliender** con branding real verificado del brand guide oficial (HEX exactos, Manrope+Inconsolata, logos reales) — bloques A–F completos → `is_client_editable == True`.

## 3. Requisitos no funcionales

- **RNF1 · Cero invención (manual §2.1).** Todo dato del seed Cliender proviene del brand guide oficial `02. RECURSOS DE MARCA CLIENDER/01. IDENTIDAD DE MARCA CLIENDER/CLIENDER_BRAND_GUIDE_CLAUDE.md`. Nada aproximado.
- **RNF2 · Contratos puros.** Modelos + completitud en `packages/contracts` (sin I/O). Loaders con I/O en `apps/engine`.
- **RNF3 · Versionado.** `schema_version` en ambos contratos.
- **RNF4 · Provenance.** Cada bloque admite `source` y `updated_at` (manual §5: "cada dato tiene fuente y fecha"). En M2 es opcional pero soportado.
- **RNF5 · Fuente de verdad = YAML en repo `playbooks/`**; espejo en OneDrive `02. PLAYBOOKS/` (docs). Supabase se conecta en M3.

---

## 4. Diseño

### 4.1 ClientProfile (bloques A–H)
```
ClientProfile
├── schema_version, client_id, name
├── identity: Identity        (A) name, slug, legal_name?, sector, location?, web?, socials{}, description[3]
├── visual:   VisualIdentity   (B) logos[], palette[ColorToken{name,hex,role}], fonts[], subtitle_style, intro_outro, moodboard
├── voice:    Voice            (C) tone[], treatment(tu|usted), languages[], approved_phrases[], blacklist{words,topics,competitors,claims}, verified_data[]
├── audience: Audience         (D) target{age,profile,pain,scroll_stopper}, default_goal, cta{text,destination}, platforms[]
├── edit_rules: EditRules      (E) authorized_playbooks[], default_playbook, durations{}, pacing{}, music{style,library[],volume_rel}, never_do[], authorized_people[]
├── library:  Library          (F) broll[Asset{url,description}], brand_photos[], prior_approved[], prior_rejected[], music_sfx[]
├── commercial: Commercial|None (G) services[], active_offers[], competitors[], account_manager?, approval_channel?
└── learning: Learning|None     (H) numeric_goals{}, performance_history[], learned_adjustments[]
```
Todos los bloques `Optional[...] = None` a nivel de tipo (RF2). La obligatoriedad A–F la impone `client_missing_blocks`.

### 4.2 Gate de completitud (RF3)
`client_missing_blocks` comprueba, por bloque A–F: (1) presente (no None) y (2) sus campos críticos no vacíos:
- A: `description` no vacía · B: `palette` y `fonts` no vacíos · C: `tone` y `blacklist` presentes · D: `cta` y `platforms` · E: `default_playbook` · F: bloque presente (listas pueden ir vacías, "aunque sea corta").
Devuelve p.ej. `["B.visual: palette vacía", "D.audience: falta cta"]`. Es exactamente la señal que el Pipeline Engine (M5) convierte en estado `NEEDS_INPUT`.

### 4.3 Playbook (D7)
```
Playbook
├── schema_version, id, name, platforms[]
├── beats: [Beat{name, rel_duration, purpose}]          # suma ≈ 1.0
├── hook: HookSpec{max_seconds, style, land_by_seconds}
├── subtitles: SubtitlePolicy{enabled, karaoke, emphasis, uppercase}
├── music: MusicPolicy{enabled, style, ducking, target_lufs}
├── pacing: PacingPolicy{cut_style, zoom, energy}
├── cta: CTAPolicy{enabled, position, default_text?}
├── ideal_duration: {platform: {min_s, max_s}}
└── target_metrics: {retention?: float, ctr?: float}
```

### 4.4 Módulos de código
| Fichero | Contenido |
|---|---|
| `contracts/client_profile.py` | modelos A–H + `client_missing_blocks` + `is_client_editable` |
| `contracts/playbook.py` | modelos Playbook + `validate_playbook` |
| `engine/profiles.py` | `load_client`, `load_clients_dir` (YAML→modelo) |
| `engine/playbooks.py` | `load_playbook`, `load_playbooks_dir` (actualiza el stub M0) |
| `playbooks/reel-educativo.yaml`, `podcast-clips.yaml` | semillas |
| `playbooks/clients/cliender.yaml` | cliente semilla (branding real) |

---

## 5. Interfaces (API pública)

```python
# contracts (puro)
ClientProfile, Playbook, ColorToken, Beat, ...           # modelos
client_missing_blocks(profile) -> list[str]
is_client_editable(profile) -> bool
validate_playbook(pb) -> None                            # raise PlaybookValidationError

# engine (I/O)
load_client(path) -> ClientProfile
load_clients_dir(dir) -> dict[str, ClientProfile]        # por client_id
load_playbook(path) -> Playbook
load_playbooks_dir(dir) -> dict[str, Playbook]           # por id
```

---

## 6. Modelos de datos

Ver §4.1 y §4.3. Notas:
- `ColorToken.hex` valida formato `#RRGGBB` (regex). Roles: primary/secondary/accent/bg/text.
- `treatment ∈ {tu, usted}`; `languages` códigos BCP-47 (es-ES, ca, en).
- Persistencia (M3): `ClientProfile` → tabla `clients`; `Playbook` → tabla `playbooks` o fichero versionado. En M2 solo YAML.

## 7. Casos límite

- **CL1** — Perfil sin bloque B → `client_missing_blocks` lo lista; `is_client_editable == False`.
- **CL2** — Palette con hex inválido (`#GGG`) → ValidationError en carga.
- **CL3** — Playbook con beats que suman 0.8 → `PlaybookValidationError`.
- **CL4** — YAML con clave desconocida → Pydantic la ignora (extra="ignore") salvo que se decida `forbid`; en M2 = ignore + warning documentado.
- **CL5** — Cliente completo A–F pero G/H vacíos → **editable** (G–H no bloquean).
- **CL6** — `treatment` fuera de {tu,usted} → ValidationError.

## 8. Riesgos

| Riesgo | Prob. | Mitigación |
|---|---|---|
| Inventar branding (viola manual §2) | — | Seed 100% del brand guide oficial verificado; test comprueba HEX exactos |
| Schema ClientProfile demasiado rígido | Media | Bloques opcionales a nivel tipo; completitud por función; `extra=ignore` |
| Beats mal normalizados | Baja | `validate_playbook` con tolerancia ±0.01 + test |
| Divergencia YAML repo vs Supabase futuro | Media | YAML = fuente en M2; M3 define migración/carga a PG con el mismo schema |

## 9. Tests (TDD)

- **T1** — Cliender seed carga y `is_client_editable == True`; `client_missing_blocks == []`.
- **T2** — HEX del seed == valores oficiales (`#8F7EE9`, `#1E2839`, `#14181E`, `#EBEAE4`, `#FFFFFF`); fonts == Manrope/Inconsolata (anti-invención).
- **T3** — Perfil al que se le quita bloque B/D → `is_client_editable == False` y lista el bloque (CL1).
- **T4** — `ColorToken` rechaza hex inválido (CL2); `treatment` inválido rechazado (CL6).
- **T5** — 2 playbooks semilla cargan y pasan `validate_playbook`; beats suman ≈1.0.
- **T6** — `validate_playbook` rechaza beats que no suman 1.0 (CL3) y min>max en duración.
- **T7** — `load_clients_dir`/`load_playbooks_dir` indexan por id.
- **T8** — round-trip: cargar YAML → modelo → dump → re-cargar == igual.

Cobertura objetivo M2: **≥88%**.

## 10. Plan de implementación (TDD)

1. Tests T1–T8 (rojos) sobre la API objetivo.
2. `client_profile.py`: modelos A–H + `client_missing_blocks` + `is_client_editable`.
3. `playbook.py`: modelos + `validate_playbook`.
4. `engine/profiles.py` + actualizar `engine/playbooks.py`.
5. Semillas: 2 playbooks + `clients/cliender.yaml` (branding real).
6. Verde + ruff + cobertura.
7. Espejo YAML a OneDrive `02. PLAYBOOKS/`.
8. Cierre: doc, BITACORA, memoria, commit. **F1 completada.**

## 11. Documentación / cierre

- Este doc en `01. MODULOS/`.
- Semillas espejadas en OneDrive `02. PLAYBOOKS/` (playbooks/ + clientes/).
- BITACORA entrada M2 (cierre F1); memoria `project_vios_plan.md`.
- Commit en `~/dev/vios/`.

---

## Salida esperada M2 (criterio de cierre)

✅ ClientProfile A–H + gate de completitud · ✅ Playbook + validación · ✅ loader YAML · ✅ 2 playbooks semilla + cliente Cliender con branding real verificado · ✅ tests T1–T8 verdes, cobertura ≥88% · ✅ **F1 (Contratos) cerrada** → siguiente F2 (Ingesta: M3 media pipeline, M4 MediaIntelligence).
