# D8-learning-async — Learning loop asíncrono y separado

- **Estado:** aceptada (confirmar/impugnar en F0)
- **Fecha:** 2026-07-16
- **Origen:** plan maestro §1

## Contexto
Las métricas llegan días después de publicar; es otro dominio (analytics).

## Decisión
El learning loop es un pipeline separado del motor de edición, ingesta batch.

## Consecuencias
Motor simple; aprendizaje evoluciona aparte. No hay feedback inline.
