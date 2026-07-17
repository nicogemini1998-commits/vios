"""M10: marker thumbnail + effect cta_overlay + speech_ranges_in_timeline."""
from vios_contracts import (
    EFFECT_CTA_OVERLAY,
    KNOWN_EFFECTS,
    MediaIntelligence,
    Segment,
    TimelineDraft,
    Transcript,
    speech_ranges_in_timeline,
    validate,
)

from .builders import base_ir


def make_intel(segments):
    return {
        "asset-a": MediaIntelligence(
            asset_id="asset-a", source_hash="h1", duration_s=120.0,
            transcript=Transcript(language="es", segments=segments),
        ),
    }


def two_cut_ir():
    """2 cortes de asset-a: [300,390)→0-90 y [600,660)→90-150 (fps 30)."""
    d = TimelineDraft.from_ir(base_ir())
    vt = d.add_track("video")
    d.add_clip(vt, source="asset-a", start=0, in_point=300, out_point=390)
    d.add_clip(vt, source="asset-a", start=90, in_point=600, out_point=660)
    return d.commit(by="edit-agent", why="fixture 2 cortes")


def test_marker_thumbnail_valido():
    d = TimelineDraft.from_ir(base_ir())
    d.add_marker("thumbnail", at=0, label="candidato",
                 payload={"asset_id": "asset-a", "source_frame": 315})
    ir = d.commit(by="cta-agent", why="thumbnail candidato")
    validate(ir)
    assert ir.markers[0].kind == "thumbnail"


def test_catalogo_effects_m10():
    assert EFFECT_CTA_OVERLAY == "cta_overlay"
    assert EFFECT_CTA_OVERLAY in KNOWN_EFFECTS
    assert len(KNOWN_EFFECTS) == 5


def test_speech_ranges_remapea_y_clampea():
    # segmento 10.0-13.0s = source 300-390 → clip 1 entero (0-90)
    # segmento 19.5-21.5s = source 585-645 → cruza el corte: clampeado a 600-645
    # → 90-135, adyacente al anterior → fusionado
    intel = make_intel([
        Segment(start_s=10.0, end_s=13.0, text="hook"),
        Segment(start_s=19.5, end_s=21.5, text="cruza el corte"),
    ])
    assert speech_ranges_in_timeline(two_cut_ir(), intel) == [(0, 135)]

    # sin el primer segmento se ve el clamp aislado: 90-135
    intel = make_intel([Segment(start_s=19.5, end_s=21.5, text="cruza el corte")])
    assert speech_ranges_in_timeline(two_cut_ir(), intel) == [(90, 135)]


def test_speech_ranges_fusiona_solapados():
    intel = make_intel([
        Segment(start_s=10.0, end_s=11.0, text="a"),      # 300-330 → 0-30
        Segment(start_s=11.0, end_s=12.0, text="b"),      # 330-360 → 30-60 (adyacente)
    ])
    assert speech_ranges_in_timeline(two_cut_ir(), intel) == [(0, 60)]


def test_speech_ranges_sin_transcript_vacio():
    assert speech_ranges_in_timeline(two_cut_ir(), make_intel([])) == []
    assert speech_ranges_in_timeline(two_cut_ir(), {}) == []
