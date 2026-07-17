"""F4 (M8): extensión TimelineDraft + aritmética de tiempo canónica + remapeo."""
import pytest
from builders import build_reel
from vios_contracts import (
    TimelineDraft,
    frames_to_s,
    s_to_frames,
    source_frame_to_timeline,
)

# --- s_to_frames / frames_to_s (única aritmética de fps permitida) ---

def test_s_to_frames_redondea():
    assert s_to_frames(0.0, 30) == 0
    assert s_to_frames(1.5, 30) == 45
    assert s_to_frames(1.0166, 30) == 30   # round, no truncado
    assert s_to_frames(1.99, 30) == 60


def test_frames_to_s_inversa():
    assert frames_to_s(0, 30) == 0.0
    assert frames_to_s(45, 30) == 1.5
    assert frames_to_s(s_to_frames(2.4, 25), 25) == pytest.approx(2.4, abs=1 / 25)


def test_conversion_fps_invalido():
    with pytest.raises(ValueError):
        s_to_frames(1.0, 0)
    with pytest.raises(ValueError):
        frames_to_s(10, 0)


# --- TimelineDraft.add_clip_effect ---

def test_add_clip_effect_happy():
    ir1 = build_reel()
    d = TimelineDraft.from_ir(ir1)
    d.add_clip_effect("v0", "c0", {"type": "zoom", "params": {"scale_to": 1.2}})
    ir2 = d.commit(by="t", why="zoom en corte 1")
    clip = ir2.tracks[0].clips[0]
    assert [e.type for e in clip.effects] == ["zoom"]
    assert clip.effects[0].params == {"scale_to": 1.2}
    # append, no reemplazo
    d2 = TimelineDraft.from_ir(ir2)
    d2.add_clip_effect("v0", "c0", {"type": "subtitle_style", "params": {}})
    ir3 = d2.commit(by="t", why="estilo")
    assert [e.type for e in ir3.tracks[0].clips[0].effects] == ["zoom", "subtitle_style"]
    # la IR base nunca muta
    assert ir1.tracks[0].clips[0].effects == []


def test_add_clip_effect_inexistente():
    d = TimelineDraft.from_ir(build_reel())
    with pytest.raises(KeyError):
        d.add_clip_effect("v0", "nope", {"type": "zoom", "params": {}})
    with pytest.raises(KeyError):
        d.add_clip_effect("nope", "c0", {"type": "zoom", "params": {}})


# --- TimelineDraft.set_clip_transform ---

def test_set_clip_transform_happy():
    ir1 = build_reel()
    d = TimelineDraft.from_ir(ir1)
    d.set_clip_transform("v0", "c1", {"scale": 1.3, "x": 10, "y": -20})
    ir2 = d.commit(by="t", why="reencuadre corte 2")
    t = ir2.tracks[0].clips[1].transform
    assert (t.scale, t.x, t.y) == (1.3, 10, -20)
    # defaults pydantic para campos no pasados
    assert t.rotation == 0.0 and t.opacity == 1.0
    # base intacta
    assert ir1.tracks[0].clips[1].transform.scale == 1.0


def test_set_clip_transform_inexistente():
    d = TimelineDraft.from_ir(build_reel())
    with pytest.raises(KeyError):
        d.set_clip_transform("v0", "nope", {"scale": 2.0})


# --- source_frame_to_timeline (remapeo source → timeline, compartido F4) ---
# build_reel: video v0 con asset-a en [0,90) → timeline 0-90 y [300,450) → timeline 90-240.

def test_remapeo_dentro_de_clip():
    ir = build_reel()
    assert source_frame_to_timeline(ir, "asset-a", 0) == 0
    assert source_frame_to_timeline(ir, "asset-a", 89) == 89
    assert source_frame_to_timeline(ir, "asset-a", 300) == 90    # clip 2, in_point=300
    assert source_frame_to_timeline(ir, "asset-a", 449) == 239


def test_remapeo_material_cortado():
    ir = build_reel()
    assert source_frame_to_timeline(ir, "asset-a", 90) is None    # out_point exclusivo
    assert source_frame_to_timeline(ir, "asset-a", 150) is None   # entre cortes
    assert source_frame_to_timeline(ir, "asset-a", 450) is None


def test_remapeo_asset_desconocido_y_solo_video():
    ir = build_reel()
    assert source_frame_to_timeline(ir, "no-existe", 10) is None
    # el track subtitle usa texto como source: no debe remapearse
    assert source_frame_to_timeline(ir, "Hola, esto es un reel", 10) is None
