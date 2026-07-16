"""Grafo de fases (D2) — declarativo, con orden topológico determinista.

El grafo VIOS es fijo por diseño (D2: grafo explícito, no orquestación LLM).
F3 cubre hasta `edit`; F4/F5 añaden capas y render sin tocar el motor.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PipelineGraphError(ValueError):
    """Grafo mal formado: dependencia desconocida o ciclo."""


class PhaseSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    deps: tuple[str, ...] = ()
    max_attempts: int = Field(default=2, ge=1)


class PipelineGraph:
    def __init__(self, phases: list[PhaseSpec]) -> None:
        names = [p.name for p in phases]
        if len(names) != len(set(names)):
            raise PipelineGraphError(f"fases duplicadas: {names}")
        self._by_name = {p.name: p for p in phases}
        for p in phases:
            for d in p.deps:
                if d not in self._by_name:
                    raise PipelineGraphError(f"fase '{p.name}': dep desconocida '{d}'")
        self._order = self._topo_sort(phases)

    def _topo_sort(self, phases: list[PhaseSpec]) -> list[str]:
        # Kahn preservando el orden de declaración (determinista).
        pending = {p.name: set(p.deps) for p in phases}
        order: list[str] = []
        while pending:
            ready = [n for n in pending if not pending[n]]
            if not ready:
                raise PipelineGraphError(f"ciclo detectado entre: {sorted(pending)}")
            declared = [p.name for p in phases if p.name in ready]
            nxt = declared[0]
            order.append(nxt)
            del pending[nxt]
            for deps in pending.values():
                deps.discard(nxt)
        return order

    @property
    def order(self) -> list[str]:
        return list(self._order)

    def spec(self, name: str) -> PhaseSpec:
        return self._by_name[name]

    def __contains__(self, name: str) -> bool:
        return name in self._by_name


def vios_default_graph() -> PipelineGraph:
    """Grafo F3: ingest → director → story → edit. F4+ añade capas paralelas."""
    return PipelineGraph([
        PhaseSpec(name="ingest"),
        PhaseSpec(name="director", deps=("ingest",)),
        PhaseSpec(name="story", deps=("director",)),
        PhaseSpec(name="edit", deps=("story",)),
    ])
