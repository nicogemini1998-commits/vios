# D1-timeline-ir — Timeline IR como contrato central

- **Estado:** aceptada (confirmar/impugnar en F0)
- **Fecha:** 2026-07-16
- **Origen:** plan maestro §1

## Contexto
Los agentes necesitan un punto único de verdad sobre la edición. Editar props de Remotion directamente acopla razonamiento a render.

## Decisión
La edición se representa como una IR declarativa (JSON Schema versionado, inmutable por revisiones). Agentes escriben revisiones; renderers la materializan.

## Consecuencias
Desacople total, auditable y diffable, testeable sin renderizar. Coste: diseñar bien la IR (riesgo #1, mitigado en M1 con golden tests).
