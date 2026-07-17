"""Genera el golden `reel_f4_rev7.json`: la IR del e2e F4 completo (revisión 7).

Mismos datos que el golden brief e2e de test_agents.py, sin LLM (EditPlan directo).
Ejecutar desde apps/engine: `uv run python tests/make_golden_rev7.py`.
"""
from pathlib import Path

from vios_contracts import (
    Asset,
    Audience,
    Beat,
    ClientCTA,
    ClientProfile,
    ClientSubtitleStyle,
    CTAPolicy,
    DurationRange,
    EditPlan,
    EditRules,
    HookCandidate,
    HookSpec,
    Library,
    LogoRef,
    MediaIntelligence,
    MusicPolicy,
    MusicRules,
    Playbook,
    Scene,
    Segment,
    SelectedMoment,
    SubtitlePolicy,
    Transcript,
    VisualIdentity,
    to_json,
)
from vios_engine.agents import (
    AudioMusicAgent,
    BrandingAgent,
    BRollAgent,
    CTAThumbnailAgent,
    EditAgent,
    SubtitleAgent,
    VisualMotionAgent,
)

GOLDEN = (Path(__file__).resolve().parents[3]
          / "packages" / "contracts" / "tests" / "golden" / "reel_f4_rev7.json")


def make_fixtures():
    """Fixtures canónicas del e2e (reutilizadas por los tests de QA M12)."""
    playbook = Playbook(
        id="reel-educativo", name="Reel educativo",
        beats=[Beat(name="hook", rel_duration=0.1),
               Beat(name="desarrollo", rel_duration=0.73),
               Beat(name="cta", rel_duration=0.17)],
        hook=HookSpec(max_seconds=3.5),
        subtitles=SubtitlePolicy(enabled=True, karaoke=False),
        music=MusicPolicy(enabled=True, ducking=True),
        cta=CTAPolicy(enabled=True, position="end", default_text="Sígueme"),
        ideal_duration={"instagram": DurationRange(min_s=15, max_s=60)},
    )
    client = ClientProfile(
        client_id="cliender", name="Cliender",
        visual=VisualIdentity(
            logos=[LogoRef(name="logo1b", file="logo1b.png")],
            subtitle_style=ClientSubtitleStyle(font="Inter", color_base="#FFFFFF"),
        ),
        edit_rules=EditRules(music=MusicRules(volume_rel=0.7)),
        audience=Audience(cta=ClientCTA(text="Reserva tu llamada",
                                        destination="cliender.com")),
        library=Library(music_sfx=[Asset(url="music-1.mp3")],
                        broll=[Asset(url="broll-1.mp4", description="oficina")]),
    )
    intel = {
        "a1": MediaIntelligence(
            asset_id="a1", source_hash="h1", duration_s=120.0,
            width=1920, height=1080,
            transcript=Transcript(language="es", segments=[
                Segment(start_s=10.0, end_s=13.0, text="¿Sabías que el 80% falla?"),
                Segment(start_s=20.0, end_s=42.0, text="La clave es el sistema..."),
                Segment(start_s=50.0, end_s=55.0, text="Sígueme para más."),
            ]),
            scenes=[Scene(index=0, start_s=0.0, end_s=60.0),
                    Scene(index=1, start_s=60.0, end_s=120.0)],
        ),
        "music-1.mp3": MediaIntelligence(asset_id="music-1.mp3", source_hash="hm",
                                         duration_s=45.0),
        "broll-1.mp4": MediaIntelligence(asset_id="broll-1.mp4", source_hash="hb",
                                         duration_s=2.0, width=1920, height=1080),
    }
    plan = EditPlan(
        project_id="p1", client_id="cliender", playbook_id="reel-educativo",
        platform="instagram", intent="educar", arc="p→s→c",
        target_duration_s=30.0,
        moments=[
            SelectedMoment(order=0, asset_id="a1", start_s=10.0, end_s=13.0,
                           beat="hook", why="gancho"),
            SelectedMoment(order=1, asset_id="a1", start_s=20.0, end_s=42.0,
                           beat="desarrollo", why="núcleo"),
            SelectedMoment(order=2, asset_id="a1", start_s=50.0, end_s=55.0,
                           beat="cta", why="cierre"),
        ],
        hooks=[HookCandidate(asset_id="a1", start_s=10.0, end_s=13.0,
                             text="¿Sabías?", score=0.9)],
    )

    return playbook, client, intel, plan


def run_f4(ir_edit, intel, playbook, client, constraints=None):
    """Cadena F4 completa sobre la IR de edit (la re-usa el loop de QA M12)."""
    ir = SubtitleAgent().add_subtitles(ir_edit, intel, playbook, client,
                                       constraints=constraints)
    ir = BrandingAgent().apply_branding(ir, client, playbook, intel_by_asset=intel)
    ir = VisualMotionAgent().apply_motion(ir, intel, playbook, client)
    ir = AudioMusicAgent().apply_music(ir, intel, playbook, client,
                                       constraints=constraints)
    ir = BRollAgent().apply_broll(ir, intel, playbook, client,
                                  constraints=constraints)
    return CTAThumbnailAgent().apply_cta(ir, playbook, client,
                                         constraints=constraints)


def build_rev7():
    playbook, client, intel, plan = make_fixtures()
    ir_edit = EditAgent(fps=30).build_timeline(plan, playbook)
    ir = run_f4(ir_edit, intel, playbook, client)
    assert ir.revision == 7, f"esperada revisión 7, obtenida {ir.revision}"
    return ir


if __name__ == "__main__":
    ir = build_rev7()
    GOLDEN.write_text(to_json(ir) + "\n", encoding="utf-8")
    print(f"golden escrito: {GOLDEN} (revisión {ir.revision})")
