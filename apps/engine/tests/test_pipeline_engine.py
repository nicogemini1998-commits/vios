"""Tests M5: grafo de fases, retries, budget, checkpoints."""
import pytest
from vios_contracts import Canvas, create_timeline
from vios_engine.pipeline import (
    BudgetExceededError,
    InMemoryCheckpointStore,
    JobState,
    PhaseResult,
    PhaseSpec,
    PipelineContext,
    PipelineEngine,
    PipelineGraph,
    PipelineGraphError,
    TokenBudget,
    vios_default_graph,
)

# --- grafo ---

def test_default_graph_order():
    g = vios_default_graph()
    assert g.order == ["ingest", "director", "story", "edit", "subtitle", "branding",
                       "visual", "audio", "broll", "cta", "qa", "render"]


def test_graph_cycle_detected():
    with pytest.raises(PipelineGraphError, match="ciclo"):
        PipelineGraph([
            PhaseSpec(name="a", deps=("b",)),
            PhaseSpec(name="b", deps=("a",)),
        ])


def test_graph_unknown_dep():
    with pytest.raises(PipelineGraphError, match="dep desconocida"):
        PipelineGraph([PhaseSpec(name="a", deps=("nope",))])


def test_graph_duplicate_phase():
    with pytest.raises(PipelineGraphError, match="duplicadas"):
        PipelineGraph([PhaseSpec(name="a"), PhaseSpec(name="a")])


# --- budget ---

def test_budget_charge_and_exceed():
    b = TokenBudget(100)
    b.charge(60)
    assert b.remaining == 40
    with pytest.raises(BudgetExceededError):
        b.charge(50)


# --- motor ---

def make_ctx(graph, budget_limit=10_000):
    job = JobState.new("j1", "p1", graph.order)
    return PipelineContext(job=job, budget=TokenBudget(budget_limit))


def make_ir(revision_agent="test"):
    ir = create_timeline("p1", 30, Canvas(width=1080, height=1920, aspect="9:16"),
                         "instagram", "reel-educativo")
    return ir


async def test_happy_path_runs_all_phases_in_order():
    graph = vios_default_graph()
    seen: list[str] = []

    def handler(name):
        async def h(ctx):
            seen.append(name)
            return PhaseResult(output=name, tokens_used=10)
        return h

    engine = PipelineEngine(graph, {n: handler(n) for n in graph.order},
                            InMemoryCheckpointStore())
    ctx = make_ctx(graph)
    job = await engine.run(ctx)
    assert job.status == "done"
    assert seen == graph.order
    assert job.tokens_spent == 120
    assert all(p.status == "done" for p in job.phases.values())


async def test_retry_then_success():
    graph = PipelineGraph([PhaseSpec(name="only", max_attempts=3)])
    attempts = {"n": 0}

    async def flaky(ctx):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("boom")
        return PhaseResult(output="ok")

    engine = PipelineEngine(graph, {"only": flaky}, InMemoryCheckpointStore())
    job = await engine.run(make_ctx(graph))
    assert job.status == "done"
    assert job.phases["only"].attempts == 3


async def test_fail_after_max_attempts():
    graph = PipelineGraph([PhaseSpec(name="only", max_attempts=2)])

    async def always_fails(ctx):
        raise RuntimeError("kaputt")

    engine = PipelineEngine(graph, {"only": always_fails}, InMemoryCheckpointStore())
    job = await engine.run(make_ctx(graph))
    assert job.status == "failed"
    assert "kaputt" in job.error
    assert job.phases["only"].attempts == 2


async def test_budget_exceeded_aborts_without_retry():
    graph = PipelineGraph([
        PhaseSpec(name="a", max_attempts=5),
        PhaseSpec(name="b", deps=("a",)),
    ])
    calls = {"a": 0, "b": 0}

    async def expensive(ctx):
        calls["a"] += 1
        return PhaseResult(output="x", tokens_used=200)

    async def never(ctx):
        calls["b"] += 1
        return PhaseResult()

    engine = PipelineEngine(graph, {"a": expensive, "b": never},
                            InMemoryCheckpointStore())
    job = await engine.run(make_ctx(graph, budget_limit=100))
    assert job.status == "failed"
    assert "budget" in job.error
    assert calls["a"] == 1          # sin reintento tras budget
    assert calls["b"] == 0          # fase posterior no corre


async def test_checkpoint_saved_when_phase_produces_ir():
    graph = PipelineGraph([PhaseSpec(name="edit")])
    store = InMemoryCheckpointStore()

    async def edits(ctx):
        return PhaseResult(output="done", ir=make_ir())

    engine = PipelineEngine(graph, {"edit": edits}, store)
    ctx = make_ctx(graph)
    job = await engine.run(ctx)
    assert job.status == "done"
    assert len(store.saved) == 1
    assert store.saved[0][0] == "j1"
    assert store.saved[0][1] == "edit"
    assert ctx.ir is not None
    assert await store.latest("p1") is not None


def test_missing_handler_rejected():
    graph = vios_default_graph()
    with pytest.raises(ValueError, match="sin handler"):
        PipelineEngine(graph, {}, InMemoryCheckpointStore())
