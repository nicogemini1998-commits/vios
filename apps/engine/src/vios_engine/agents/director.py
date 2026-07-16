"""Director Agent (M6): brief + intelligence + playbook + cliente → EditPlan base.

Produce intención, estructura de beats resuelta en segundos y duración objetivo.
Eval-first: la salida se valida con `validate_edit_plan` (parcial, sin momentos);
si el JSON no parsea o no valida, UN reintento con el error en el prompt.
"""
from __future__ import annotations

import json

from vios_contracts import (
    ClientProfile,
    EditPlan,
    MediaIntelligence,
    Playbook,
    validate_edit_plan,
)

from .llm import LLMClient, LLMParseError, extract_json

_SYSTEM = (
    "Eres el Director de edición de vídeo de VIOS. Decides la intención y la "
    "estructura de un vídeo corto a partir del brief del cliente, el playbook "
    "y el análisis del material bruto. Respondes SOLO con un objeto JSON válido, "
    "sin texto adicional."
)

_PROMPT = """BRIEF:
{brief}

CLIENTE: {client_name} — tono: {tone}
PLATAFORMA OBJETIVO: {platform}

PLAYBOOK "{playbook_name}":
- beats (fracción del total): {beats}
- hook: máx {hook_max}s
- duración ideal en {platform}: {dur_min}-{dur_max}s

MATERIAL DISPONIBLE:
{material}

Devuelve JSON con esta forma exacta:
{{
  "intent": "qué debe lograr el vídeo (1 frase)",
  "arc": "resumen del arco narrativo (1-2 frases)",
  "target_duration_s": <float dentro del rango ideal>,
  "structure": [
    {{"name": "<nombre beat del playbook>", "purpose": "...", "target_duration_s": <float>}}
  ]
}}
Reglas: usa exactamente los beats del playbook, en su orden; las duraciones de
los beats deben sumar target_duration_s (±10%)."""


def _material_summary(intelligence: dict[str, MediaIntelligence]) -> str:
    lines = []
    for asset_id, mi in intelligence.items():
        n_scenes = len(mi.scenes)
        text = " ".join(s.text for s in mi.transcript.segments)[:500]
        lines.append(
            f"- asset {asset_id}: {mi.duration_s or '?'}s, {n_scenes} escenas, "
            f"transcript: \"{text}\""
        )
    return "\n".join(lines) or "- (sin material analizado)"


class DirectorAgent:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm
        self.tokens_used = 0

    async def plan(
        self,
        project_id: str,
        brief: str,
        client: ClientProfile,
        playbook: Playbook,
        platform: str,
        intelligence: dict[str, MediaIntelligence],
    ) -> EditPlan:
        rng = playbook.ideal_duration.get(platform)
        tone = ", ".join(client.voice.tone) if client.voice and client.voice.tone else "neutro"
        prompt_base = _PROMPT.format(
            brief=brief,
            client_name=client.name,
            tone=tone,
            platform=platform,
            playbook_name=playbook.name,
            beats=json.dumps(
                [{"name": b.name, "rel_duration": b.rel_duration} for b in playbook.beats]
            ),
            hook_max=playbook.hook.max_seconds if playbook.hook else "n/a",
            dur_min=rng.min_s if rng else 15,
            dur_max=rng.max_s if rng else 60,
            material=_material_summary(intelligence),
        )
        last_error = ""
        for _ in range(2):  # intento + 1 reintento con feedback
            prompt = prompt_base if not last_error else (
                prompt_base + f"\nTu respuesta anterior falló: {last_error}. Corrige."
            )
            result = await self._llm.complete(_SYSTEM, prompt)
            self.tokens_used += result.tokens_total
            try:
                data = extract_json(result.text)
                plan = EditPlan(
                    project_id=project_id,
                    client_id=client.client_id,
                    playbook_id=playbook.id,
                    platform=platform,
                    intent=str(data.get("intent", "")),
                    arc=str(data.get("arc", "")),
                    target_duration_s=float(data["target_duration_s"]),
                    structure=data.get("structure", []),
                )
                # validación parcial: aún sin momentos (los pone Story)
                validate_edit_plan(plan, playbook=playbook)
                return plan
            except (LLMParseError, KeyError, TypeError, ValueError) as exc:
                last_error = str(exc)
        raise LLMParseError(f"Director no produjo EditPlan válido: {last_error}")
