# D4-analisis-cacheado — Analizar una vez, editar N veces

- **Estado:** aceptada (confirmar/impugnar en F0)
- **Fecha:** 2026-07-16
- **Origen:** plan maestro §1

## Contexto
Re-analizar el bruto por cada edición es el mayor coste evitable.

## Decisión
La ingesta produce un MediaIntelligence cacheado por hash de archivo; las ediciones lo reutilizan.

## Consecuencias
Un bruto genera múltiples formatos sin re-análisis. Requiere invalidación por hash correcta.
