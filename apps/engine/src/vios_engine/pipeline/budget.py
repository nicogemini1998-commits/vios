"""Presupuesto de tokens por job (M5, riesgo 'coste LLM dispara').

Cada llamada LLM carga tokens (in+out) contra el budget del job. Si se supera,
el job aborta con BudgetExceededError — coste acotado por diseño, no por fe.
"""
from __future__ import annotations


class BudgetExceededError(RuntimeError):
    """El job superó su presupuesto de tokens."""


class TokenBudget:
    def __init__(self, limit: int) -> None:
        if limit <= 0:
            raise ValueError("limit debe ser > 0")
        self._limit = limit
        self._spent = 0

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def spent(self) -> int:
        return self._spent

    @property
    def remaining(self) -> int:
        return max(0, self._limit - self._spent)

    def charge(self, tokens: int) -> None:
        """Carga tokens gastados. Lanza BudgetExceededError si supera el límite."""
        if tokens < 0:
            raise ValueError("tokens debe ser >= 0")
        self._spent += tokens
        if self._spent > self._limit:
            raise BudgetExceededError(
                f"presupuesto agotado: {self._spent}/{self._limit} tokens"
            )
