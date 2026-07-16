"""Capa LLM de los agentes (M6). Cliente intercambiable: real (Anthropic) o fake.

Los agentes piden JSON estricto y reportan tokens usados para el budget del job
(M5). El cliente real usa el SDK de Anthropic; los tests usan FakeLLM — ninguna
prueba llama a la API.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

DEFAULT_MODEL = "claude-sonnet-5"


class LLMParseError(ValueError):
    """La respuesta del LLM no contiene JSON parseable."""


@dataclass
class LLMResult:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0

    @property
    def tokens_total(self) -> int:
        return self.tokens_in + self.tokens_out


class LLMClient(Protocol):
    async def complete(self, system: str, prompt: str, max_tokens: int = 4096) -> LLMResult: ...


class FakeLLM:
    """Cliente scriptado para tests: devuelve respuestas en orden."""

    def __init__(self, responses: list[str], tokens_per_call: int = 100) -> None:
        self._responses = list(responses)
        self._tokens = tokens_per_call
        self.calls: list[tuple[str, str]] = []

    async def complete(self, system: str, prompt: str, max_tokens: int = 4096) -> LLMResult:
        self.calls.append((system, prompt))
        if not self._responses:
            raise RuntimeError("FakeLLM sin respuestas restantes")
        text = self._responses.pop(0)
        half = self._tokens // 2
        return LLMResult(text=text, tokens_in=half, tokens_out=self._tokens - half)


class AnthropicLLM:
    """Cliente real (SDK anthropic). Import perezoso: solo si se instancia."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        from anthropic import AsyncAnthropic  # dep opcional [llm]

        if not api_key:
            raise ValueError("api_key requerida para AnthropicLLM")
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(self, system: str, prompt: str, max_tokens: int = 4096) -> LLMResult:
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return LLMResult(
            text=text,
            tokens_in=msg.usage.input_tokens,
            tokens_out=msg.usage.output_tokens,
        )


_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> dict:
    """Extrae el primer objeto JSON de una respuesta LLM (con o sin fence)."""
    candidate = text.strip()
    fence = _JSON_FENCE.search(candidate)
    if fence:
        candidate = fence.group(1).strip()
    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end <= start:
            raise LLMParseError(f"sin objeto JSON en respuesta: {text[:200]!r}")
        candidate = candidate[start:end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LLMParseError(f"JSON inválido: {exc}") from exc
