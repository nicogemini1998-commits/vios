# D7-playbooks-datos — Playbooks = datos (YAML), no código

- **Estado:** aceptada (confirmar/impugnar en F0)
- **Fecha:** 2026-07-16
- **Origen:** plan maestro §1

## Contexto
Hardcodear playbooks obliga a deployar para añadir un vertical.

## Decisión
Los playbooks son archivos YAML versionados cargados por un loader.

## Consecuencias
Añadir vertical = escribir un archivo. Requiere schema y validación robusta (M2).
