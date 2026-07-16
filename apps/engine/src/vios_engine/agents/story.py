"""Story Agent (M6): EditPlan base + transcript → momentos seleccionados + hooks.

Completa el EditPlan del Director con la selección real de momentos del bruto
(asset, rango en segundos, beat al que sirve, por qué) y candidatos a hook.
Eval-first: la salida completa pasa `validate_edit_plan` con playbook e
intelligence; JSON/validación fallida → UN reintento con el error.
"""
from __future__ import annotations

from vios_contracts import (
    EditPlan,
    MediaIntelligence,
    Playbook,
    validate_edit_plan,
)

from .llm import LLMClient, LLMParseError, extract_json

_SYSTEM = (
    "Eres el Story Agent de VIOS. Seleccionas los momentos exactos del material "
    "bruto que construyen el arco narrativo decidido por el Director. Solo puedes "
    "usar rangos que existen en el transcript; NUNCA inventes contenido. Respondes "
    "SOLO con un objeto JSON válido."
)

_PROMPT = """PLAN DEL DIRECTOR:
- intent: {intent}
- arc: {arc}
- target_duration_s: {target}
- beats: {beats}

TRANSCRIPT CON TIEMPOS (asset → segmentos [start_s-end_s] texto):
{transcript}

ESCENAS: {scenes}

Devuelve JSON con esta forma exacta:
{{
  "moments": [
    {{"order": 0, "asset_id": "...", "start_s": <float>, "end_s": <float>,
      "beat": "<nombre beat>", "why": "por qué este momento"}}
  ],
  "hooks": [
    {{"asset_id": "...", "start_s": <float>, "end_s": <float>,
      "text": "frase literal", "score": <0-1>, "why": "..."}}
  ]
}}
Reglas: orders 0..n-1 sin huecos; cada momento dentro de la duración real del
asset; la suma de momentos ≈ target_duration_s (±20%); hooks de máximo
{hook_max}s cada uno; el texto del hook debe ser literal del transcript."""


def _transcript_dump(intelligence: dict[str, MediaIntelligence]) -> str:
    lines = []
    for asset_id, mi in intelligence.items():
        lines.append(f"asset {asset_id} (duración {mi.duration_s}s):")
        for seg in mi.transcript.segments:
            flag = " [dudoso]" if seg.low_confidence else ""
            lines.append(f"  [{seg.start_s:.1f}-{seg.end_s:.1f}]{flag} {seg.text}")
    return "\n".join(lines) or "(sin transcript)"


def _scenes_dump(intelligence: dict[str, MediaIntelligence]) -> str:
    parts = []
    for asset_id, mi in intelligence.items():
        rngs = ", ".join(f"[{s.start_s:.1f}-{s.end_s:.1f}]" for s in mi.scenes)
        parts.append(f"{asset_id}: {rngs or '(sin escenas)'}")
    return " | ".join(parts)


class StoryAgent:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm
        self.tokens_used = 0

    async def select_moments(
        self,
        plan: EditPlan,
        playbook: Playbook,
        intelligence: dict[str, MediaIntelligence],
    ) -> EditPlan:
        prompt_base = _PROMPT.format(
            intent=plan.intent,
            arc=plan.arc,
            target=plan.target_duration_s,
            beats=[b.name for b in plan.structure],
            transcript=_transcript_dump(intelligence),
            scenes=_scenes_dump(intelligence),
            hook_max=playbook.hook.max_seconds if playbook.hook else 3.0,
        )
        last_error = ""
        for _ in range(2):
            prompt = prompt_base if not last_error else (
                prompt_base + f"\nTu respuesta anterior falló: {last_error}. Corrige."
            )
            result = await self._llm.complete(_SYSTEM, prompt)
            self.tokens_used += result.tokens_total
            try:
                data = extract_json(result.text)
                full = EditPlan.model_validate({
                    **plan.model_dump(),
                    "moments": data.get("moments", []),
                    "hooks": data.get("hooks", []),
                })
                validate_edit_plan(full, playbook=playbook, intelligence=intelligence)
                return full
            except (LLMParseError, KeyError, TypeError, ValueError) as exc:
                last_error = str(exc)
        raise LLMParseError(f"Story no produjo momentos válidos: {last_error}")
