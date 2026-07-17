"""Tests M8 (F4): SubtitleAgent + BrandingAgent. Deterministas, sin LLM/ML.

Fixture base: IR con 2 cortes del asset a1 — [300,390)→timeline 0-90 y
[600,660)→timeline 90-150 (fps 30, es decir 10-13s y 20-22s del bruto).
"""
import pytest
from vios_contracts import (
    Canvas,
    ClientProfile,
    ClientSubtitleStyle,
    ColorToken,
    IntroOutro,
    LogoRef,
    MediaIntelligence,
    Playbook,
    Segment,
    SubtitlePolicy,
    TimelineDraft,
    Transcript,
    VisualIdentity,
    Word,
    create_timeline,
    validate,
)
from vios_engine.agents import BrandingAgent, SubtitleAgent


def make_ir():
    base = create_timeline("p1", 30, Canvas(width=1080, height=1920, aspect="9:16"),
                           "instagram", "reel-educativo")
    d = TimelineDraft.from_ir(base)
    vt = d.add_track("video")
    d.add_clip(vt, source="a1", start=0, in_point=300, out_point=390)
    d.add_clip(vt, source="a1", start=90, in_point=600, out_point=660)
    d.add_marker("hook", at=0, label="hook")
    return d.commit(by="edit-agent", why="fixture 2 cortes")


def make_intel() -> dict[str, MediaIntelligence]:
    seg1 = Segment(start_s=10.0, end_s=13.0, text="¿Sabías que el 80% falla?", words=[
        Word(start_s=10.0, end_s=10.5, text="¿Sabías"),
        Word(start_s=10.5, end_s=10.8, text="que"),
        Word(start_s=10.8, end_s=11.0, text="el"),
        Word(start_s=11.0, end_s=11.8, text="80%"),
        Word(start_s=11.8, end_s=12.6, text="falla?"),
    ])
    # cruza el corte: "la"/"clave" quedan fuera del clip 2 (empieza en 20.0s)
    seg2 = Segment(start_s=19.5, end_s=21.5, text="la clave es sistema",
                   low_confidence=True, words=[
        Word(start_s=19.5, end_s=19.7, text="la"),
        Word(start_s=19.7, end_s=20.0, text="clave"),
        Word(start_s=20.2, end_s=20.5, text="es"),
        Word(start_s=20.5, end_s=21.0, text="sistema"),
    ])
    return {"a1": MediaIntelligence(
        asset_id="a1", source_hash="h1", duration_s=120.0,
        transcript=Transcript(language="es", segments=[seg1, seg2]),
    )}


def make_playbook(karaoke=False, enabled=True) -> Playbook:
    return Playbook(id="reel-educativo", name="Reel",
                    subtitles=SubtitlePolicy(enabled=enabled, karaoke=karaoke))


def make_profile(uppercase=False, logos=True, intro_outro=None) -> ClientProfile:
    return ClientProfile(
        client_id="cliender", name="Cliender",
        visual=VisualIdentity(
            logos=[LogoRef(name="logo1b", file="logo1b.png")] if logos else [],
            palette=[ColorToken(name="blanco", hex="#FFFFFF", role="text"),
                     ColorToken(name="acento", hex="#FF0055", role="accent")],
            subtitle_style=ClientSubtitleStyle(
                font="Inter", size_rel=1.0, color_base="#FFFFFF",
                color_emphasis="#FF0055", position="bottom", uppercase=uppercase,
            ),
            intro_outro=intro_outro,
        ),
    )


def subtitle_track(ir):
    return next((t for t in ir.tracks if t.kind == "subtitle"), None)


# --- SubtitleAgent: modo líneas ---

def test_subtitle_lineas_literal_y_mapeo():
    ir = SubtitleAgent().add_subtitles(make_ir(), make_intel(),
                                       make_playbook(), make_profile())
    validate(ir)
    assert ir.revision == 2
    st = subtitle_track(ir)
    assert st is not None
    # anti-alucinación: texto literal exacto, con signos y símbolos
    assert st.clips[0].source == "¿Sabías que el 80% falla?"
    # mapeo: word 10.0s → frame source 300 → timeline 0; fin 12.6s → timeline 78
    assert st.clips[0].start == 0
    assert st.clips[0].out_point - st.clips[0].in_point == 78
    # clip 2: solo palabras visibles ("es sistema"); "la"/"clave" caen en el corte
    assert st.clips[1].source == "es sistema"
    assert st.clips[1].start == 96          # 90 + (606-600)
    assert st.clips[1].out_point - st.clips[1].in_point == 24   # hasta 21.0s → 630 → 120
    # decisión auditada
    assert ir.meta.decisions[-1].agent == "subtitle-agent"


def test_subtitle_estilo_del_cliente_en_effect():
    ir = SubtitleAgent().add_subtitles(make_ir(), make_intel(),
                                       make_playbook(), make_profile())
    clip = subtitle_track(ir).clips[0]
    eff = next(e for e in clip.effects if e.type == "subtitle_style")
    assert eff.params["font"] == "Inter"
    assert eff.params["color_base"] == "#FFFFFF"        # hex exacto, nunca aproximado
    assert eff.params["color_emphasis"] == "#FF0055"
    assert eff.params["position"] == "bottom"


def test_subtitle_low_confidence_marcado_nunca_corregido():
    ir = SubtitleAgent().add_subtitles(make_ir(), make_intel(),
                                       make_playbook(), make_profile())
    clips = subtitle_track(ir).clips
    eff0 = next(e for e in clips[0].effects if e.type == "subtitle_style")
    eff1 = next(e for e in clips[1].effects if e.type == "subtitle_style")
    assert eff0.params.get("low_confidence", False) is False
    assert eff1.params["low_confidence"] is True


def test_subtitle_uppercase_por_estilo():
    ir = SubtitleAgent().add_subtitles(make_ir(), make_intel(),
                                       make_playbook(), make_profile(uppercase=True))
    assert subtitle_track(ir).clips[0].source == "¿SABÍAS QUE EL 80% FALLA?"


# --- SubtitleAgent: karaoke ---

def test_subtitle_karaoke_clip_por_palabra_y_omite_cortadas():
    ir = SubtitleAgent().add_subtitles(make_ir(), make_intel(),
                                       make_playbook(karaoke=True), make_profile())
    st = subtitle_track(ir)
    # 5 palabras del clip 1 + 2 visibles del clip 2 ("la"/"clave" omitidas)
    assert [c.source for c in st.clips] == [
        "¿Sabías", "que", "el", "80%", "falla?", "es", "sistema",
    ]
    w80 = st.clips[3]
    assert w80.start == 30                              # 11.0s → 330 → timeline 30
    assert w80.out_point - w80.in_point == 24           # 0.8s a 30fps


# --- SubtitleAgent: skips auditados ---

def test_subtitle_skip_transcript_vacio():
    intel = {"a1": MediaIntelligence(asset_id="a1", source_hash="h1")}
    ir = SubtitleAgent().add_subtitles(make_ir(), intel,
                                       make_playbook(), make_profile())
    assert ir.revision == 2                             # revisión igualmente (skip auditado)
    assert subtitle_track(ir) is None
    assert "skip" in ir.meta.decisions[-1].action


def test_subtitle_skip_policy_disabled():
    ir = SubtitleAgent().add_subtitles(make_ir(), make_intel(),
                                       make_playbook(enabled=False), make_profile())
    assert subtitle_track(ir) is None
    assert "skip" in ir.meta.decisions[-1].action


# --- BrandingAgent ---

def branded(profile, intel=None):
    ir = SubtitleAgent().add_subtitles(make_ir(), make_intel(),
                                       make_playbook(), make_profile())
    return BrandingAgent().apply_branding(ir, profile, make_playbook(),
                                          intel_by_asset=intel or {})


def test_branding_logo_cubre_timeline_completa():
    ir = branded(make_profile())
    validate(ir)
    assert ir.revision == 3
    gt = next(t for t in ir.tracks if t.kind == "graphic")
    logo = gt.clips[0]
    assert logo.source == "logo1b.png"
    assert logo.start == 0
    assert logo.out_point - logo.in_point == 150        # fin de timeline (2 cortes)
    eff = next(e for e in logo.effects if e.type == "logo_overlay")
    assert eff.params["corner"] == "top_right"
    assert ir.meta.decisions[-1].agent == "branding-agent"


def test_branding_sin_logo_anotado():
    ir = branded(make_profile(logos=False))
    assert not any(t.kind == "graphic" for t in ir.tracks)
    assert ir.revision == 3                             # decisión igualmente


def test_branding_no_toca_subtitulos():
    before = SubtitleAgent().add_subtitles(make_ir(), make_intel(),
                                           make_playbook(), make_profile())
    after = BrandingAgent().apply_branding(before, make_profile(), make_playbook(),
                                           intel_by_asset={})
    assert subtitle_track(after) == subtitle_track(before)


def test_branding_intro_outro_mandatory_sin_file_needs_input():
    profile = make_profile(intro_outro=IntroOutro(exists=True, file="", mandatory=True))
    with pytest.raises(ValueError, match="NEEDS_INPUT"):
        branded(profile)


def test_branding_outro_materializado_con_duracion_real():
    outro_intel = {"outro.mp4": MediaIntelligence(
        asset_id="outro.mp4", source_hash="h9", duration_s=2.0)}
    profile = make_profile(intro_outro=IntroOutro(exists=True, file="outro.mp4",
                                                  mandatory=True))
    ir = branded(profile, intel=outro_intel)
    video = next(t for t in ir.tracks if t.kind == "video")
    outro = video.clips[-1]
    assert outro.source == "outro.mp4"
    assert outro.start == 150                           # al final de la timeline
    assert outro.out_point - outro.in_point == 60       # 2.0s a 30fps, duración REAL
    # el logo cubre también el outro
    gt = next(t for t in ir.tracks if t.kind == "graphic")
    assert gt.clips[0].out_point - gt.clips[0].in_point == 210


def test_branding_outro_mandatory_sin_intel_needs_input():
    profile = make_profile(intro_outro=IntroOutro(exists=True, file="outro.mp4",
                                                  mandatory=True))
    with pytest.raises(ValueError, match="NEEDS_INPUT"):
        branded(profile, intel={})
