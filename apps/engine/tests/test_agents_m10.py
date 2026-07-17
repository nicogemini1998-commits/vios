"""Tests M10 (F4): BRollAgent + CTAThumbnailAgent. Deterministas, sin LLM/ML.

Fixture: IR 9:16 con 2 cortes de a1 — [300,390)→0-90 y [600,780)→90-270 (fps 30),
hook en 0 (a1, 10.0-12.0s), cta en 269. Voz: 10.0-13.0s (clip 1 entero) +
20.5-21.5s (→105-135) → valle grande en 135-270.
"""
from vios_contracts import (
    Asset,
    Audience,
    Canvas,
    ClientCTA,
    ClientProfile,
    ColorToken,
    CTAPolicy,
    FontRef,
    HookSpec,
    Library,
    MediaIntelligence,
    Playbook,
    Segment,
    TimelineDraft,
    Transcript,
    VisualIdentity,
    create_timeline,
    validate,
)
from vios_engine.agents import BRollAgent, CTAThumbnailAgent


def make_ir(with_cta_marker=True, with_hook=True):
    base = create_timeline("p1", 30, Canvas(width=1080, height=1920, aspect="9:16"),
                           "instagram", "reel-educativo")
    d = TimelineDraft.from_ir(base)
    vt = d.add_track("video")
    d.add_clip(vt, source="a1", start=0, in_point=300, out_point=390)
    d.add_clip(vt, source="a1", start=90, in_point=600, out_point=780)
    st = d.add_track("subtitle")
    d.add_clip(st, source="hola", start=0, in_point=0, out_point=30)
    if with_hook:
        d.add_marker("hook", at=0, label="¿Sabías?",
                     payload={"asset_id": "a1", "start_s": 10.0, "end_s": 12.0,
                              "score": 0.9})
    if with_cta_marker:
        d.add_marker("cta", at=269, label="Reserva")
    return d.commit(by="edit-agent", why="fixture 2 cortes + hook + cta")


def make_intel(segments=None, broll_analyzed=True, broll_dims=True):
    if segments is None:
        segments = [
            Segment(start_s=10.0, end_s=13.0, text="¿Sabías que el 80% falla?"),
            Segment(start_s=20.5, end_s=21.5, text="la clave es sistema"),
        ]
    intel = {
        "a1": MediaIntelligence(asset_id="a1", source_hash="h1", duration_s=120.0,
                                transcript=Transcript(language="es", segments=segments)),
    }
    if broll_analyzed:
        intel["broll-1.mp4"] = MediaIntelligence(
            asset_id="broll-1.mp4", source_hash="hb1", duration_s=2.0,
            width=1920 if broll_dims else None, height=1080 if broll_dims else None)
        intel["broll-2.mp4"] = MediaIntelligence(
            asset_id="broll-2.mp4", source_hash="hb2", duration_s=5.0,
            width=1920 if broll_dims else None, height=1080 if broll_dims else None)
    return intel


def make_playbook(cta_enabled=True, cta_text="", hook_max_s=3.0):
    return Playbook(id="reel-educativo", name="Reel",
                    hook=HookSpec(max_seconds=hook_max_s),
                    cta=CTAPolicy(enabled=cta_enabled, position="end",
                                  default_text=cta_text))


def make_profile(broll=True, cta=True, visual=True):
    return ClientProfile(
        client_id="cliender", name="Cliender",
        visual=VisualIdentity(
            fonts=[FontRef(family="Inter", usage="cuerpo"),
                   FontRef(family="Archivo Black", usage="cta")],
            palette=[ColorToken(name="lima", hex="#C6FF00", role="accent")],
        ) if visual else None,
        audience=Audience(cta=ClientCTA(text="Reserva tu llamada",
                                        destination="cliender.com")) if cta else None,
        library=Library(broll=[Asset(url="broll-1.mp4", description="oficina"),
                               Asset(url="broll-2.mp4", description="equipo")]
                        if broll else []),
    )


def video_tracks(ir):
    return [t for t in ir.tracks if t.kind == "video"]


def graphic_tracks(ir):
    return [t for t in ir.tracks if t.kind == "graphic"]


# --- BRollAgent ---

def test_broll_rellena_valle_con_asset_real():
    ir = BRollAgent().apply_broll(make_ir(), make_intel(),
                                  make_playbook(), make_profile())
    validate(ir)
    assert ir.revision == 2
    overlay = video_tracks(ir)[1]                       # track nuevo encima del base
    assert len(overlay.clips) == 1
    clip = overlay.clips[0]
    assert clip.source == "broll-1.mp4"
    assert clip.start == 135                            # valle tras la voz 105-135
    assert clip.out_point - clip.in_point == 60         # min(2.0s reales, valle 135f)
    assert clip.transform.scale == 1.7778               # cover 16:9 → 9:16
    assert ir.meta.decisions[-1].agent == "broll-agent"


def test_broll_round_robin_en_varios_valles():
    segments = [
        Segment(start_s=10.0, end_s=13.0, text="clip 1 entero"),
        Segment(start_s=20.5, end_s=21.5, text="a"),    # → 105-135
        Segment(start_s=24.0, end_s=25.0, text="b"),    # → 210-240
    ]
    ir = BRollAgent().apply_broll(make_ir(), make_intel(segments=segments),
                                  make_playbook(), make_profile())
    overlay = video_tracks(ir)[1]
    assert [c.source for c in overlay.clips] == ["broll-1.mp4", "broll-2.mp4"]
    assert [c.start for c in overlay.clips] == [135, 240]


def test_broll_valle_menor_que_minimo_ignorado():
    # voz 20.5-25.5s cubre 105-255 → huecos [90,105) y [255,270) de 15f (0.5s)
    segments = [Segment(start_s=10.0, end_s=13.0, text="clip 1"),
                Segment(start_s=20.5, end_s=25.5, text="casi todo el clip 2")]
    ir = BRollAgent().apply_broll(make_ir(), make_intel(segments=segments),
                                  make_playbook(), make_profile())
    assert len(video_tracks(ir)) == 1
    assert "sin valles" in ir.meta.decisions[-1].why


def test_broll_protege_el_hook():
    # voz solo en 10.5-12.0s → valle [60,90) dentro de la ventana de hook (90f)
    segments = [Segment(start_s=10.5, end_s=12.0, text="hook parcial"),
                Segment(start_s=20.0, end_s=26.0, text="clip 2 entero")]
    ir = BRollAgent().apply_broll(make_ir(), make_intel(segments=segments),
                                  make_playbook(hook_max_s=3.0), make_profile())
    for track in video_tracks(ir)[1:]:
        for clip in track.clips:
            assert clip.start >= 90                     # nunca sobre el hook


def test_broll_biblioteca_vacia_skip():
    ir = BRollAgent().apply_broll(make_ir(), make_intel(),
                                  make_playbook(), make_profile(broll=False))
    assert len(video_tracks(ir)) == 1
    assert "skip" in ir.meta.decisions[-1].action


def test_broll_asset_sin_analisis_usa_siguiente():
    intel = make_intel()
    del intel["broll-1.mp4"]                            # sin duración real → no se usa
    ir = BRollAgent().apply_broll(make_ir(), intel, make_playbook(), make_profile())
    overlay = video_tracks(ir)[1]
    assert overlay.clips[0].source == "broll-2.mp4"
    assert "broll-1.mp4" in ir.meta.decisions[-1].why   # anotado el descarte


def test_broll_sin_dims_sin_transform():
    ir = BRollAgent().apply_broll(make_ir(), make_intel(broll_dims=False),
                                  make_playbook(), make_profile())
    clip = video_tracks(ir)[1].clips[0]
    assert clip.transform.scale == 1.0                  # nunca escalar a ciegas
    assert "sin dimensiones" in ir.meta.decisions[-1].why


def test_broll_video_mudo_skip():
    ir = BRollAgent().apply_broll(make_ir(), make_intel(segments=[]),
                                  make_playbook(), make_profile())
    assert len(video_tracks(ir)) == 1
    assert "skip" in ir.meta.decisions[-1].action


def test_broll_no_toca_subtitulos_ni_video_base():
    before = make_ir()
    after = BRollAgent().apply_broll(before, make_intel(),
                                     make_playbook(), make_profile())
    assert video_tracks(after)[0] == video_tracks(before)[0]
    subs_before = next(t for t in before.tracks if t.kind == "subtitle")
    subs_after = next(t for t in after.tracks if t.kind == "subtitle")
    assert subs_after == subs_before


# --- CTAThumbnailAgent ---

def test_cta_overlay_con_copy_de_la_ficha():
    ir = CTAThumbnailAgent().apply_cta(make_ir(), make_playbook(cta_text="Sígueme"),
                                       make_profile())
    validate(ir)
    assert ir.revision == 2
    clip = graphic_tracks(ir)[0].clips[0]
    assert clip.source == "Reserva tu llamada"          # ficha gana al playbook
    assert clip.start == 180                            # 3s antes del fin (270)
    assert clip.out_point - clip.in_point == 90
    fx = next(e for e in clip.effects if e.type == "cta_overlay")
    assert fx.params["text"] == "Reserva tu llamada"
    assert fx.params["destination"] == "cliender.com"
    assert fx.params["font"] == "Archivo Black"         # usage "cta" de la ficha
    assert fx.params["color"] == "#C6FF00"              # rol accent de la palette
    assert ir.meta.decisions[-1].agent == "cta-agent"


def test_cta_fallback_al_default_del_playbook():
    ir = CTAThumbnailAgent().apply_cta(make_ir(), make_playbook(cta_text="Sígueme"),
                                       make_profile(cta=False))
    assert graphic_tracks(ir)[0].clips[0].source == "Sígueme"


def test_cta_sin_texto_omitido():
    ir = CTAThumbnailAgent().apply_cta(make_ir(), make_playbook(cta_text=""),
                                       make_profile(cta=False))
    assert graphic_tracks(ir) == []
    assert "sin copy" in ir.meta.decisions[-1].why


def test_cta_disabled_omitido():
    ir = CTAThumbnailAgent().apply_cta(make_ir(), make_playbook(cta_enabled=False),
                                       make_profile())
    assert graphic_tracks(ir) == []


def test_cta_ficha_sin_font_ni_color_campos_vacios():
    ir = CTAThumbnailAgent().apply_cta(make_ir(), make_playbook(),
                                       make_profile(visual=False))
    fx = next(e for e in graphic_tracks(ir)[0].clips[0].effects
              if e.type == "cta_overlay")
    assert fx.params["font"] == "" and fx.params["color"] == ""


def test_thumbnail_desde_el_hook():
    ir = CTAThumbnailAgent().apply_cta(make_ir(), make_playbook(), make_profile())
    thumb = next(m for m in ir.markers if m.kind == "thumbnail")
    # punto medio del hook 10.0-12.0s → source 330 → timeline 30
    assert thumb.payload == {"asset_id": "a1", "source_frame": 330}
    assert thumb.at == 30


def test_thumbnail_sin_hook_usa_primer_clip():
    ir = CTAThumbnailAgent().apply_cta(make_ir(with_hook=False),
                                       make_playbook(), make_profile())
    thumb = next(m for m in ir.markers if m.kind == "thumbnail")
    # punto medio del primer clip [300,390) → source 345 → timeline 45
    assert thumb.payload == {"asset_id": "a1", "source_frame": 345}
    assert thumb.at == 45


def test_cta_timeline_vacia_skip():
    base = create_timeline("p1", 30, Canvas(width=1080, height=1920, aspect="9:16"),
                           "instagram", "reel-educativo")
    ir = CTAThumbnailAgent().apply_cta(base, make_playbook(), make_profile())
    assert graphic_tracks(ir) == []
    assert "skip" in ir.meta.decisions[-1].action
