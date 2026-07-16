# D9-standalone — VIOS standalone; CDPro consumidor futuro

- **Estado:** aceptada (confirmar/impugnar en F0)
- **Fecha:** 2026-07-16
- **Origen:** plan maestro §1

## Contexto
CDPro es un frontend creativo con deuda propia; extenderlo contamina el núcleo.

## Decisión
VIOS nace standalone con núcleo limpio; comparte servicios con CDPro (Remotion, Supabase), no codebase. A futuro CDPro consume VIOS.

## Consecuencias
Libertad de diseño; coste de no reutilizar UI existente a corto plazo.
