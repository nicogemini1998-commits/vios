"""Tests M6 (Director+Story, FakeLLM) y M7 (Edit Agent) + golden brief e2e.

Eval-first: ningún test llama a la API real; el FakeLLM scripta respuestas y
los validadores de contrato son el harness (validate_edit_plan / validate IR).
"""
import json

import pytest
from vios_contracts import (
    Beat,
    ClientProfile,
    CTAPolicy,
    DurationRange,
    EditPlan,
    HookCandidate,
    HookSpec,
    MediaIntelligence,
    PlannedBeat,
    Playbook,
    Scene,
    Segment,
    SelectedMoment,
    Transcript,
    validate,
    validate_edit_plan,
)
from vios_engine.agents import DirectorAgent, EditAgent, FakeLLM, LLMParseError, StoryAgent
from vios_engine.agents.llm import extract_json

# --- fixtures sintéticas ---

def make_playbook() -> Playbook:
    return Playbook(
        id="reel-educativo",
        name="Reel educativo",
        beats=[
            Beat(name="hook", rel_duration=0.1),
            Beat(name="desarrollo", rel_duration=0.73),
            Beat(name="cta", rel_duration=0.17),
        ],
        hook=HookSpec(max_seconds=3.5),
        cta=CTAPolicy(enabled=True, position="end", default_text="Sígueme"),
        ideal_duration={"instagram": DurationRange(min_s=15, max_s=60)},
    )


def make_client() -> ClientProfile:
    return ClientProfile(client_id="cliender", name="Cliender")


def make_intelligence() -> dict[str, MediaIntelligence]:
    return {
        "a1": MediaIntelligence(
            asset_id="a1",
            source_hash="h1",
            duration_s=120.0,
            transcript=Transcript(language="es", segments=[
                Segment(start_s=10.0, end_s=13.0, text="¿Sabías que el 80% falla?"),
                Segment(start_s=20.0, end_s=42.0, text="La clave es el sistema..."),
                Segment(start_s=50.0, end_s=55.0, text="Sígueme para más."),
            ]),
            scenes=[Scene(index=0, start_s=0.0, end_s=60.0),
                    Scene(index=1, start_s=60.0, end_s=120.0)],
        )
    }


DIRECTOR_JSON = json.dumps({
    "intent": "educar sobre sistemas de venta",
    "arc": "problema → solución → llamada",
    "target_duration_s": 30.0,
    "structure": [
        {"name": "hook", "purpose": "gancho", "target_duration_s": 3.0},
        {"name": "desarrollo", "purpose": "núcleo", "target_duration_s": 22.0},
        {"name": "cta", "purpose": "cierre", "target_duration_s": 5.0},
    ],
})

STORY_JSON = json.dumps({
    "moments": [
        {"order": 0, "asset_id": "a1", "start_s": 10.0, "end_s": 13.0,
         "beat": "hook", "why": "dato que frena el scroll"},
        {"order": 1, "asset_id": "a1", "start_s": 20.0, "end_s": 42.0,
         "beat": "desarrollo", "why": "explicación núcleo"},
        {"order": 2, "asset_id": "a1", "start_s": 50.0, "end_s": 55.0,
         "beat": "cta", "why": "cierre natural"},
    ],
    "hooks": [
        {"asset_id": "a1", "start_s": 10.0, "end_s": 13.0,
         "text": "¿Sabías que el 80% falla?", "score": 0.9, "why": "dato + pregunta"},
    ],
})


# --- extract_json ---

def test_extract_json_plain_and_fenced():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('bla {"a": 1} bla') == {"a": 1}
    with pytest.raises(LLMParseError):
        extract_json("sin json")


# --- provider LLM (suscripción por defecto) ---

class _FakeBlock:
    def __init__(self, text):
        self.text = text


class _FakeAssistant:
    def __init__(self, texts):
        self.content = [_FakeBlock(t) for t in texts]


class _FakeResult:
    def __init__(self, usage, is_error=False, result=None):
        self.usage = usage
        self.is_error = is_error
        self.result = result


def test_parse_agent_messages_collects_text_and_usage():
    from vios_engine.agents import parse_agent_messages

    msgs = [
        _FakeAssistant(["{\"a\": ", "1}"]),
        _FakeResult({"input_tokens": 120, "output_tokens": 40}),
    ]
    res = parse_agent_messages(msgs)
    assert res.text == '{"a": 1}'
    assert res.tokens_in == 120
    assert res.tokens_out == 40
    assert res.tokens_total == 160


def test_parse_agent_messages_raises_on_error_result():
    from vios_engine.agents import parse_agent_messages

    with pytest.raises(RuntimeError, match="rate"):
        parse_agent_messages([_FakeResult({}, is_error=True, result="rate limit")])


def test_build_llm_defaults_to_subscription(monkeypatch):
    import vios_engine.agents.llm as llm_mod

    # evita el import real del SDK: solo comprobamos la rama de selección
    monkeypatch.setattr(llm_mod.ClaudeAgentLLM, "__init__",
                        lambda self, model=llm_mod.DEFAULT_MODEL: None)
    client = llm_mod.build_llm("subscription")
    assert isinstance(client, llm_mod.ClaudeAgentLLM)


def test_build_llm_unknown_provider():
    from vios_engine.agents import build_llm

    with pytest.raises(ValueError, match="desconocido"):
        build_llm("gpt")


# --- Director (M6) ---

async def test_director_produces_valid_plan():
    llm = FakeLLM([DIRECTOR_JSON])
    agent = DirectorAgent(llm)
    plan = await agent.plan("p1", "haz un reel educativo", make_client(),
                            make_playbook(), "instagram", make_intelligence())
    assert plan.target_duration_s == 30.0
    assert [b.name for b in plan.structure] == ["hook", "desarrollo", "cta"]
    assert agent.tokens_used > 0


async def test_director_retries_on_bad_json_then_succeeds():
    llm = FakeLLM(["esto no es json", DIRECTOR_JSON])
    agent = DirectorAgent(llm)
    plan = await agent.plan("p1", "brief", make_client(), make_playbook(),
                            "instagram", make_intelligence())
    assert plan.intent
    assert len(llm.calls) == 2
    assert "falló" in llm.calls[1][1]      # feedback del error en el reintento


async def test_director_fails_after_two_bad_responses():
    llm = FakeLLM(["nada", "tampoco"])
    agent = DirectorAgent(llm)
    with pytest.raises(LLMParseError, match="Director"):
        await agent.plan("p1", "brief", make_client(), make_playbook(),
                         "instagram", make_intelligence())


async def test_director_rejects_duration_out_of_playbook():
    bad = json.loads(DIRECTOR_JSON)
    bad["target_duration_s"] = 500.0
    bad["structure"] = [{"name": "hook", "target_duration_s": 500.0}]
    llm = FakeLLM([json.dumps(bad), json.dumps(bad)])
    with pytest.raises(LLMParseError):
        await DirectorAgent(llm).plan("p1", "brief", make_client(), make_playbook(),
                                      "instagram", make_intelligence())


# --- Story (M6) ---

def make_base_plan() -> EditPlan:
    return EditPlan(
        project_id="p1", client_id="cliender", playbook_id="reel-educativo",
        platform="instagram", intent="educar", arc="p→s→c",
        target_duration_s=30.0,
        structure=[
            PlannedBeat(name="hook", target_duration_s=3.0),
            PlannedBeat(name="desarrollo", target_duration_s=22.0),
            PlannedBeat(name="cta", target_duration_s=5.0),
        ],
    )


async def test_story_fills_moments_and_hooks():
    llm = FakeLLM([STORY_JSON])
    agent = StoryAgent(llm)
    full = await agent.select_moments(make_base_plan(), make_playbook(),
                                      make_intelligence())
    assert len(full.moments) == 3
    assert full.hooks[0].score == 0.9
    validate_edit_plan(full, playbook=make_playbook(),
                       intelligence=make_intelligence())


async def test_story_rejects_moment_beyond_asset():
    bad = json.loads(STORY_JSON)
    bad["moments"][1]["end_s"] = 500.0   # asset dura 120s
    llm = FakeLLM([json.dumps(bad), json.dumps(bad)])
    with pytest.raises(LLMParseError, match="Story"):
        await StoryAgent(llm).select_moments(make_base_plan(), make_playbook(),
                                             make_intelligence())


# --- Edit Agent (M7) ---

def full_plan() -> EditPlan:
    plan = make_base_plan()
    return plan.model_copy(update={
        "moments": [
            SelectedMoment(order=0, asset_id="a1", start_s=10.0, end_s=13.0,
                           beat="hook", why="gancho"),
            SelectedMoment(order=1, asset_id="a1", start_s=20.0, end_s=42.0,
                           beat="desarrollo", why="núcleo"),
            SelectedMoment(order=2, asset_id="a1", start_s=50.0, end_s=55.0,
                           beat="cta", why="cierre"),
        ],
        "hooks": [HookCandidate(asset_id="a1", start_s=10.0, end_s=13.0,
                                text="¿Sabías?", score=0.9)],
    })


def test_edit_agent_builds_coherent_timeline():
    ir = EditAgent(fps=30).build_timeline(full_plan(), make_playbook())
    validate(ir)
    assert ir.revision == 1
    video = next(t for t in ir.tracks if t.kind == "video")
    audio = next(t for t in ir.tracks if t.kind == "audio")
    assert len(video.clips) == 3
    assert len(audio.clips) == 3
    # clips consecutivos sin huecos: 3s + 22s + 5s a 30fps
    assert [c.start for c in video.clips] == [0, 90, 750]
    assert video.clips[0].in_point == 300 and video.clips[0].out_point == 390
    # duración total = 30s = 900 frames
    last = video.clips[-1]
    assert last.start + (last.out_point - last.in_point) == 900
    # markers: 3 beats + hook + cta
    kinds = [m.kind for m in ir.markers]
    assert kinds.count("beat") == 3
    assert kinds.count("hook") == 1
    assert kinds.count("cta") == 1
    # decisión auditada
    assert ir.meta.decisions[-1].agent == "edit-agent"


def test_edit_agent_requires_moments():
    with pytest.raises(ValueError, match="sin momentos"):
        EditAgent().build_timeline(make_base_plan())


# --- Golden brief e2e (F3 completo con FakeLLM) ---

async def test_golden_brief_pipeline_bruto_a_timeline(tmp_path):
    """El hito F3+F4: brief + intelligence → EditPlan → IR con las 4 capas de producción."""
    from vios_contracts import (
        Asset,
        Audience,
        ClientCTA,
        ClientSubtitleStyle,
        CTAPolicy,
        EditRules,
        Library,
        LogoRef,
        MusicPolicy,
        MusicRules,
        SubtitlePolicy,
        VisualIdentity,
    )
    from vios_engine.agents import (
        AudioMusicAgent,
        BrandingAgent,
        BRollAgent,
        CTAThumbnailAgent,
        SubtitleAgent,
        VisualMotionAgent,
    )
    from vios_engine.pipeline import (
        InMemoryCheckpointStore,
        JobState,
        PhaseResult,
        PipelineContext,
        PipelineEngine,
        TokenBudget,
        vios_default_graph,
    )
    from vios_engine.render import (
        FakeFfmpegRunner,
        InMemoryRenderRepo,
        RenderQueue,
        RenderService,
    )

    playbook = make_playbook().model_copy(update={
        "subtitles": SubtitlePolicy(enabled=True, karaoke=False),
        "music": MusicPolicy(enabled=True, ducking=True),
        "cta": CTAPolicy(enabled=True, position="end", default_text="Sígueme"),
    })
    client = make_client().model_copy(update={
        "visual": VisualIdentity(
            logos=[LogoRef(name="logo1b", file="logo1b.png")],
            subtitle_style=ClientSubtitleStyle(font="Inter", color_base="#FFFFFF"),
        ),
        "edit_rules": EditRules(music=MusicRules(volume_rel=0.7)),
        "audience": Audience(cta=ClientCTA(text="Reserva tu llamada",
                                           destination="cliender.com")),
        "library": Library(music_sfx=[Asset(url="music-1.mp3")],
                           broll=[Asset(url="broll-1.mp4", description="oficina")]),
    })
    intel = make_intelligence()
    intel["a1"] = intel["a1"].model_copy(update={"width": 1920, "height": 1080})
    intel["music-1.mp3"] = MediaIntelligence(asset_id="music-1.mp3",
                                             source_hash="hm", duration_s=45.0)
    intel["broll-1.mp4"] = MediaIntelligence(asset_id="broll-1.mp4", source_hash="hb",
                                             duration_s=2.0, width=1920, height=1080)
    director = DirectorAgent(FakeLLM([DIRECTOR_JSON]))
    story = StoryAgent(FakeLLM([STORY_JSON]))
    editor = EditAgent(fps=30)
    subtitler = SubtitleAgent()
    brander = BrandingAgent()
    visualist = VisualMotionAgent()
    musician = AudioMusicAgent()
    broller = BRollAgent()
    ctaist = CTAThumbnailAgent()

    async def h_ingest(ctx):
        return PhaseResult(output=intel)

    async def h_director(ctx):
        plan = await director.plan("p1", "haz un reel educativo", client,
                                   playbook, "instagram", ctx.outputs["ingest"])
        return PhaseResult(output=plan, tokens_used=director.tokens_used)

    async def h_story(ctx):
        full = await story.select_moments(ctx.outputs["director"], playbook,
                                          ctx.outputs["ingest"])
        return PhaseResult(output=full, tokens_used=story.tokens_used)

    async def h_edit(ctx):
        ir = editor.build_timeline(ctx.outputs["story"], playbook)
        return PhaseResult(output=ir, ir=ir)

    async def h_subtitle(ctx):
        ir = subtitler.add_subtitles(ctx.ir, ctx.outputs["ingest"], playbook, client)
        return PhaseResult(output=ir, ir=ir)

    async def h_branding(ctx):
        ir = brander.apply_branding(ctx.ir, client, playbook,
                                    intel_by_asset=ctx.outputs["ingest"])
        return PhaseResult(output=ir, ir=ir)

    async def h_visual(ctx):
        ir = visualist.apply_motion(ctx.ir, ctx.outputs["ingest"], playbook, client)
        return PhaseResult(output=ir, ir=ir)

    async def h_audio(ctx):
        ir = musician.apply_music(ctx.ir, ctx.outputs["ingest"], playbook, client)
        return PhaseResult(output=ir, ir=ir)

    async def h_broll(ctx):
        ir = broller.apply_broll(ctx.ir, ctx.outputs["ingest"], playbook, client)
        return PhaseResult(output=ir, ir=ir)

    async def h_cta(ctx):
        ir = ctaist.apply_cta(ctx.ir, playbook, client)
        return PhaseResult(output=ir, ir=ir)

    renderer = RenderService(InMemoryRenderRepo(), FakeFfmpegRunner(),
                             RenderQueue(2, 1), tmp_path, timeout_s=5.0)
    asset_paths = {"a1": "/assets/a1", "music-1.mp3": "/assets/music-1.mp3",
                   "logo1b.png": "/assets/logo1b.png",
                   "broll-1.mp4": "/assets/broll-1.mp4"}

    async def h_render(ctx):
        rec = await renderer.render(ctx.ir, "preview", "instagram",
                                    client.client_id, asset_paths,
                                    font_files={"Inter": "/fonts/Inter.ttf"})
        return PhaseResult(output={"render_id": rec.id, "url": rec.url,
                                   "status": rec.status})

    graph = vios_default_graph()
    store = InMemoryCheckpointStore()
    engine = PipelineEngine(
        graph,
        {"ingest": h_ingest, "director": h_director, "story": h_story,
         "edit": h_edit, "subtitle": h_subtitle, "branding": h_branding,
         "visual": h_visual, "audio": h_audio, "broll": h_broll, "cta": h_cta,
         "render": h_render},
        store,
    )
    ctx = PipelineContext(job=JobState.new("j1", "p1", graph.order),
                          budget=TokenBudget(10_000))
    job = await engine.run(ctx)

    assert job.status == "done"
    assert job.tokens_spent > 0
    ir = ctx.ir
    assert ir is not None
    validate(ir)
    # eval del resultado: duración dentro del rango del playbook
    video = next(t for t in ir.tracks if t.kind == "video")
    total_frames = sum(c.out_point - c.in_point for c in video.clips)
    total_s = total_frames / ir.fps
    rng = playbook.ideal_duration["instagram"]
    assert rng.min_s <= total_s <= rng.max_s
    # capas F4 completas: 6 capas — una revisión por fase
    assert ir.revision == 7
    subs = next(t for t in ir.tracks if t.kind == "subtitle")
    assert subs.clips[0].source == "¿Sabías que el 80% falla?"
    graphic = next(t for t in ir.tracks if t.kind == "graphic")
    assert graphic.clips[0].source == "logo1b.png"
    # visual: bruto 16:9 reencuadrado al canvas 9:16
    assert video.clips[0].transform.scale > 1.7
    # audio: música real de la biblioteca con mix
    music_track = [t for t in ir.tracks if t.kind == "audio"][-1]
    assert music_track.clips[0].source == "music-1.mp3"
    mix = next(e for e in music_track.clips[0].effects if e.type == "music_mix")
    assert mix.params["volume_rel"] == 0.7 and mix.params["duck_ranges"]
    # cta: overlay con el copy real de la ficha + thumbnail anotado
    cta_track = [t for t in ir.tracks if t.kind == "graphic"][-1]
    assert cta_track.clips[0].source == "Reserva tu llamada"
    assert any(m.kind == "thumbnail" for m in ir.markers)
    agents = [d.agent for d in ir.meta.decisions]
    assert agents == ["edit-agent", "subtitle-agent", "branding-agent",
                      "visual-agent", "audio-agent", "broll-agent", "cta-agent"]
    # checkpoint IR persistido por cada fase que produce timeline
    assert len(store.saved) == 7
    # render (F5): preview producida SIN nueva revisión — el render no edita
    assert ctx.outputs["render"]["status"] == "done"
    assert ctx.outputs["render"]["url"].endswith(".mp4")
    assert ir.revision == 7
