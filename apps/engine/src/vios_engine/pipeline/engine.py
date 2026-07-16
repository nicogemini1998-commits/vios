"""Motor de pipeline (M5): ejecuta el grafo de fases con retries y budget.

Un handler por fase: `async def handler(ctx) -> PhaseResult`. El motor recorre
el orden topológico, reintenta según PhaseSpec.max_attempts, carga tokens al
budget y persiste checkpoint IR cuando la fase devuelve una.
BudgetExceededError NO se reintenta: reintentar gastaría aún más.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from vios_contracts import TimelineIR

from .budget import BudgetExceededError, TokenBudget
from .checkpoints import CheckpointStore
from .graph import PipelineGraph
from .models import JobState


@dataclass
class PhaseResult:
    output: Any = None
    ir: TimelineIR | None = None       # si la fase produce/actualiza timeline
    tokens_used: int = 0


@dataclass
class PipelineContext:
    """Estado compartido entre fases de un job."""
    job: JobState
    budget: TokenBudget
    outputs: dict[str, Any] = field(default_factory=dict)   # phase → output
    ir: TimelineIR | None = None                             # última IR conocida
    extras: dict[str, Any] = field(default_factory=dict)     # brief, playbook, etc.


PhaseHandler = Callable[[PipelineContext], Awaitable[PhaseResult]]


class PipelineEngine:
    def __init__(
        self,
        graph: PipelineGraph,
        handlers: dict[str, PhaseHandler],
        checkpoints: CheckpointStore,
    ) -> None:
        missing = [n for n in graph.order if n not in handlers]
        if missing:
            raise ValueError(f"fases sin handler: {missing}")
        self._graph = graph
        self._handlers = handlers
        self._checkpoints = checkpoints

    async def run(self, ctx: PipelineContext) -> JobState:
        """Ejecuta el job completo. Devuelve el JobState final (done|failed)."""
        job = ctx.job
        job.status = "running"
        for name in self._graph.order:
            spec = self._graph.spec(name)
            phase = job.phases[name]
            job.current_phase = name
            phase.status = "running"
            last_error = ""
            while phase.attempts < spec.max_attempts:
                phase.attempts += 1
                try:
                    result = await self._handlers[name](ctx)
                except BudgetExceededError as exc:
                    return self._fail(job, name, f"budget: {exc}")
                except Exception as exc:  # noqa: BLE001 — cualquier fallo de fase reintenta
                    last_error = str(exc)
                    continue
                if result.tokens_used:
                    try:
                        ctx.budget.charge(result.tokens_used)
                    except BudgetExceededError as exc:
                        job.tokens_spent = ctx.budget.spent
                        return self._fail(job, name, f"budget: {exc}")
                job.tokens_spent = ctx.budget.spent
                ctx.outputs[name] = result.output
                if result.ir is not None:
                    ctx.ir = result.ir
                    await self._checkpoints.save(job.job_id, name, result.ir)
                phase.status = "done"
                break
            else:
                return self._fail(
                    job, name,
                    f"agotados {spec.max_attempts} intentos: {last_error}",
                )
        job.status = "done"
        job.current_phase = ""
        return job

    def _fail(self, job: JobState, phase_name: str, error: str) -> JobState:
        phase = job.phases[phase_name]
        phase.status = "failed"
        phase.error = error
        job.status = "failed"
        job.error = f"{phase_name}: {error}"
        return job
