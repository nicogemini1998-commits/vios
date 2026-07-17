"""Tests M9 (F4): VisualMotionAgent + AudioMusicAgent. Deterministas, sin LLM/ML.

Fixture: IR 9:16 con 2 cortes de a1 — [300,390)→0-90 y [600,660)→90-150 (fps 30),
beats en 0 y 90. a1 es 16:9 (1920x1080) → candidato a reframe.
"""
import pytest
from vios_contracts import (
    Asset,
    Canvas,
    ClientProfile,
    EditRules,
    Library,
    MediaIntelligence,
    MusicPolicy,
    MusicRules,
    Pacing,
    PacingPolicy,
    Playbook,
    Segment,
    TimelineDraft,
    Transcript,
    create_timeline,
    validate,
)
from vios_engine.agents import AudioMusicAgent, VisualMotionAgent


def make_ir():
    base = create_timeline("p1", 30, Canvas(width=1080, height=1920, aspect="9:16"),
                           "instagram", "reel-educativo")
    d = TimelineDraft.from_ir(base)
    vt = d.add_track("video")
    d.add_clip(vt, source="a1", start=0, in_point=300, out_point=390)
    d.add_clip(vt, source="a1", start=90, in_point=600, out_point=660)
    st = d.add_track("subtitle")
    d.add_clip(st, source="hola", start=0, in_point=0, out_point=30)
    d.add_marker("beat", at=0, label="hook")
    d.add_marker("beat", at=90, label="desarrollo")
    return d.commit(by="edit-agent", why="fixture 2 cortes + beats")


def make_intel(width=1920, height=1080, with_speech=True, music_duration=3.0):
    segments = []
    if with_speech:
        segments = [
            Segment(start_s=10.0, end_s=13.0, text="¿Sabías que el 80% falla?"),
            Segment(start_s=19.5, end_s=21.5, text="la clave es sistema"),
        ]
    return {
        "a1": MediaIntelligence(asset_id="a1", source_hash="h1", duration_s=120.0,
                                width=width, height=height,
                                transcript=Transcript(language="es", segments=segments)),
        "music-1.mp3": MediaIntelligence(asset_id="music-1.mp3", source_hash="h2",
                                         duration_s=music_duration),
    }


def make_playbook(zoom=False, cut_style="medium", music_enabled=True, ducking=True):
    return Playbook(id="reel-educativo", name="Reel",
                    pacing=PacingPolicy(zoom=zoom, cut_style=cut_style),
                    music=MusicPolicy(enabled=music_enabled, ducking=ducking))


def make_profile(music=True, zooms=False):
    return ClientProfile(
        client_id="cliender", name="Cliender",
        edit_rules=EditRules(pacing=Pacing(zooms=zooms),
                             music=MusicRules(volume_rel=0.8)),
        library=Library(music_sfx=[Asset(url="music-1.mp3")] if music else []),
    )


def video_track(ir):
    return next(t for t in ir.tracks if t.kind == "video")


def audio_tracks(ir):
    return [t for t in ir.tracks if t.kind == "audio"]


# --- VisualMotionAgent: reframe ---

def test_visual_reframe_16_9_a_9_16():
    ir = VisualMotionAgent().apply_motion(make_ir(), make_intel(),
                                          make_playbook(), make_profile())
    validate(ir)
    assert ir.revision == 2
    for clip in video_track(ir).clips:
        # cover: max(1080/1920, 1920/1080) = 1.7778, centrado
        assert clip.transform.scale == pytest.approx(1.7778, rel=1e-3)
        assert clip.transform.x == 0 and clip.transform.y == 0
    assert ir.meta.decisions[-1].agent == "visual-agent"


def test_visual_source_ya_vertical_sin_transform():
    ir = VisualMotionAgent().apply_motion(make_ir(), make_intel(width=1080, height=1920),
                                          make_playbook(), make_profile())
    for clip in video_track(ir).clips:
        assert clip.transform.scale == 1.0


def test_visual_sin_dimensiones_omitido_y_anotado():
    ir = VisualMotionAgent().apply_motion(make_ir(), make_intel(width=None, height=None),
                                          make_playbook(), make_profile())
    for clip in video_track(ir).clips:
        assert clip.transform.scale == 1.0          # nunca escalar a ciegas
    assert "sin dimensiones" in ir.meta.decisions[-1].why


# --- VisualMotionAgent: zooms ---

def test_visual_zooms_en_beats_alternados():
    ir = VisualMotionAgent().apply_motion(make_ir(),
                                          make_intel(width=1080, height=1920),
                                          make_playbook(zoom=True, cut_style="aggressive"),
                                          make_profile())
    clips = video_track(ir).clips
    z0 = next(e for e in clips[0].effects if e.type == "zoom")
    z1 = next(e for e in clips[1].effects if e.type == "zoom")
    assert z0.params == {"scale_from": 1.0, "scale_to": 1.08}      # aggressive
    assert z1.params == {"scale_from": 1.08, "scale_to": 1.0}      # alternado


def test_visual_zoom_por_ficha_con_intensidad_playbook():
    ir = VisualMotionAgent().apply_motion(make_ir(),
                                          make_intel(width=1080, height=1920),
                                          make_playbook(zoom=False, cut_style="calm"),
                                          make_profile(zooms=True))
    z0 = next(e for e in video_track(ir).clips[0].effects if e.type == "zoom")
    assert z0.params["scale_to"] == 1.03                           # calm


def test_visual_zoom_desactivado_sin_effects():
    ir = VisualMotionAgent().apply_motion(make_ir(),
                                          make_intel(width=1080, height=1920),
                                          make_playbook(zoom=False), make_profile())
    for clip in video_track(ir).clips:
        assert not any(e.type == "zoom" for e in clip.effects)


def test_visual_no_toca_subtitulos():
    before = make_ir()
    after = VisualMotionAgent().apply_motion(before, make_intel(),
                                             make_playbook(zoom=True), make_profile())
    subs_before = next(t for t in before.tracks if t.kind == "subtitle")
    subs_after = next(t for t in after.tracks if t.kind == "subtitle")
    assert subs_after == subs_before


# --- AudioMusicAgent: música ---

def test_audio_musica_con_duracion_real():
    ir = AudioMusicAgent().apply_music(make_ir(), make_intel(music_duration=3.0),
                                       make_playbook(), make_profile())
    validate(ir)
    assert ir.revision == 2
    music = audio_tracks(ir)[0].clips[0]
    assert music.source == "music-1.mp3"
    assert music.start == 0
    assert music.out_point - music.in_point == 90    # 3.0s reales, no el fin (150)
    mix = next(e for e in music.effects if e.type == "music_mix")
    assert mix.params["volume_rel"] == 0.8           # MusicRules de la ficha
    assert mix.params["target_lufs"] == -14.0
    assert ir.meta.decisions[-1].agent == "audio-agent"


def test_audio_musica_mas_larga_que_timeline_recortada():
    ir = AudioMusicAgent().apply_music(make_ir(), make_intel(music_duration=10.0),
                                       make_playbook(), make_profile())
    music = audio_tracks(ir)[0].clips[0]
    assert music.out_point - music.in_point == 150   # recorta al fin de timeline


def test_audio_biblioteca_vacia_skip():
    ir = AudioMusicAgent().apply_music(make_ir(), make_intel(),
                                       make_playbook(), make_profile(music=False))
    assert audio_tracks(ir) == []
    assert "skip" in ir.meta.decisions[-1].action


def test_audio_policy_disabled_skip():
    ir = AudioMusicAgent().apply_music(make_ir(), make_intel(),
                                       make_playbook(music_enabled=False), make_profile())
    assert audio_tracks(ir) == []
    assert "skip" in ir.meta.decisions[-1].action


def test_audio_musica_sin_analisis_skip():
    intel = make_intel()
    del intel["music-1.mp3"]                          # sin duración real → no se inventa
    ir = AudioMusicAgent().apply_music(make_ir(), intel,
                                       make_playbook(), make_profile())
    assert audio_tracks(ir) == []
    assert "skip" in ir.meta.decisions[-1].action


# --- AudioMusicAgent: ducking ---

def test_audio_ducking_rangos_remapeados_y_fusionados():
    ir = AudioMusicAgent().apply_music(make_ir(), make_intel(music_duration=10.0),
                                       make_playbook(ducking=True), make_profile())
    mix = next(e for e in audio_tracks(ir)[0].clips[0].effects if e.type == "music_mix")
    # seg1 10-13s ∩ clip1 → timeline 0-90; seg2 19.5-21.5s ∩ clip2 (clamp) → 90-135;
    # adyacentes → fusionados
    assert mix.params["ducking"] is True
    assert mix.params["duck_ranges"] == [{"start": 0, "end": 135}]


def test_audio_ducking_video_mudo_sin_rangos():
    ir = AudioMusicAgent().apply_music(make_ir(), make_intel(with_speech=False),
                                       make_playbook(ducking=True), make_profile())
    mix = next(e for e in audio_tracks(ir)[0].clips[0].effects if e.type == "music_mix")
    assert mix.params["duck_ranges"] == []


def test_audio_sin_ducking():
    ir = AudioMusicAgent().apply_music(make_ir(), make_intel(),
                                       make_playbook(ducking=False), make_profile())
    mix = next(e for e in audio_tracks(ir)[0].clips[0].effects if e.type == "music_mix")
    assert mix.params["ducking"] is False
    assert mix.params["duck_ranges"] == []
