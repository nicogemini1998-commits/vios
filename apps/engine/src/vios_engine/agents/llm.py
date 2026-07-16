"""Capa LLM de los agentes (M6). Cliente intercambiable, provider configurable.

Los agentes piden JSON estricto y reportan tokens usados para el budget del job
(M5). Providers:
  - "subscription" (DEFAULT): ClaudeAgentLLM sobre Claude Agent SDK → usa el
    login de Claude Code (suscripción Max), NO gasta créditos de API.
  - "api": AnthropicLLM sobre el SDK anthropic → factura por token. Solo para
    escala 24/7 donde el rate limit de la suscripción no basta.
Los tests usan FakeLLM — ninguna prueba llama a un modelo real.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

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


def parse_agent_messages(messages: list[Any]) -> LLMResult:
    """Extrae texto + tokens del stream del Claude Agent SDK (duck typing).

    No importa los tipos del SDK: reconoce AssistantMessage por `.content`
    (bloques con `.text`) y ResultMessage por `.usage` — así es testeable sin
    el SDK instalado y estable si el SDK renombra clases.
    """
    parts: list[str] = []
    usage: dict[str, Any] = {}
    error = ""
    for m in messages:
        content = getattr(m, "content", None)
        if isinstance(content, list):
            for block in content:
                text = getattr(block, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        u = getattr(m, "usage", None)
        if isinstance(u, dict):
            usage = u
        if getattr(m, "is_error", False):
            error = getattr(m, "result", None) or "error en Claude Agent SDK"
    if error:
        raise RuntimeError(error)
    return LLMResult(
        text="".join(parts),
        tokens_in=int(usage.get("input_tokens", 0)),
        tokens_out=int(usage.get("output_tokens", 0)),
    )


class ClaudeAgentLLM:
    """Cliente sobre Claude Agent SDK — usa la suscripción de Claude Code.

    Requiere Claude Code instalado y autenticado (login OAuth de la suscripción)
    en la máquina donde corre el engine. No consume API tokens facturados.
    Import perezoso: solo si se instancia (dep opcional [llm]).
    """

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        import claude_agent_sdk  # noqa: F401 — falla temprano si no está instalado

        self._model = model

    async def complete(self, system: str, prompt: str, max_tokens: int = 4096) -> LLMResult:
        from claude_agent_sdk import ClaudeAgentOptions, query

        options = ClaudeAgentOptions(
            system_prompt=system,
            model=self._model,
            max_turns=1,            # one-shot: sin loop agéntico
            allowed_tools=[],       # los agentes M6 solo generan JSON, sin herramientas
        )
        messages = [m async for m in query(prompt=prompt, options=options)]
        return parse_agent_messages(messages)


class AnthropicLLM:
    """Cliente API (SDK anthropic) — factura por token. Import perezoso.

    Solo para escala 24/7 donde el rate limit de la suscripción no basta;
    el default del sistema es ClaudeAgentLLM (suscripción).
    """

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        from anthropic import AsyncAnthropic  # dep opcional [llm-api]

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


def build_llm(provider: str, api_key: str = "", model: str = DEFAULT_MODEL) -> LLMClient:
    """Factory: 'subscription' (default, usa Claude Code) o 'api' (factura tokens)."""
    if provider == "subscription":
        return ClaudeAgentLLM(model=model)
    if provider == "api":
        return AnthropicLLM(api_key=api_key, model=model)
    raise ValueError(f"provider LLM desconocido: {provider!r} (usa 'subscription' o 'api')")


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
