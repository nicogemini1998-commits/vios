# D5-python-node-split — Python motor/análisis · Node/Remotion render

- **Estado:** aceptada (confirmar/impugnar en F0)
- **Fecha:** 2026-07-16
- **Origen:** plan maestro §1

## Contexto
El ecosistema ML (Whisper, PySceneDetect, librosa) es Python; Remotion exige Node.

## Decisión
Motor y análisis en Python (FastAPI); render en Node/Remotion; MCP fino en Python encima.

## Consecuencias
Dos runtimes (ya es el patrón CDPro). Frontera clara vía servicios HTTP.
