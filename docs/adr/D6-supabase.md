# D6-supabase — Postgres (Supabase) + Storage, proyecto nuevo VIOS

- **Estado:** aceptada (confirmar/impugnar en F0)
- **Fecha:** 2026-07-16
- **Origen:** plan maestro §1

## Contexto
CDPro ya domina Supabase (auth, storage URLs, backups). Mezclar datos acoplaría proyectos.

## Decisión
Supabase en patrón CDPro pero instancia NUEVA dedicada a VIOS. Media siempre por URL, nunca base64.

## Consecuencias
Núcleo limpio (coherente con D9). Menos superficie nueva, misma disciplina.
