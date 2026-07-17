"""M9: dimensiones del source en MediaIntelligence + effects zoom/music_mix."""
from vios_contracts import (
    EFFECT_MUSIC_MIX,
    EFFECT_ZOOM,
    KNOWN_EFFECTS,
    MediaIntelligence,
)


def test_media_intelligence_dimensiones():
    mi = MediaIntelligence(asset_id="a1", source_hash="h1", width=1920, height=1080)
    assert (mi.width, mi.height) == (1920, 1080)
    # opcionales: intel antigua sin dims sigue siendo válida
    old = MediaIntelligence(asset_id="a2", source_hash="h2")
    assert old.width is None and old.height is None


def test_catalogo_effects_m9():
    assert EFFECT_ZOOM == "zoom"
    assert EFFECT_MUSIC_MIX == "music_mix"
    assert {EFFECT_ZOOM, EFFECT_MUSIC_MIX} <= KNOWN_EFFECTS
