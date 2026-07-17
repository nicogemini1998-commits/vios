"""Catálogo cerrado de effect types (F4). Ningún agente inventa strings ad-hoc.

Cada tipo documenta el shape de sus params; el render (F5) es el consumidor.
"""
from __future__ import annotations

# Estilo de subtítulo aplicado por el SubtitleAgent a cada clip del track subtitle.
# params: font, size_rel, color_base, color_emphasis, position, uppercase,
#         karaoke (bool), low_confidence (bool).
EFFECT_SUBTITLE_STYLE = "subtitle_style"

# Overlay de logo aplicado por el BrandingAgent al clip del track graphic.
# params: file, corner, margin_rel.
EFFECT_LOGO_OVERLAY = "logo_overlay"

# Zoom de ritmo aplicado por el VisualMotionAgent a clips de vídeo (M9).
# params: scale_from, scale_to.
EFFECT_ZOOM = "zoom"

# Mezcla de música aplicada por el AudioMusicAgent al clip de música (M9).
# params: volume_rel, target_lufs, ducking (bool), duck_ranges ([{start, end}] en frames).
EFFECT_MUSIC_MIX = "music_mix"

# Overlay de CTA aplicado por el CTAThumbnailAgent al clip del track graphic (M10).
# params: text, destination, position, font, color.
EFFECT_CTA_OVERLAY = "cta_overlay"

KNOWN_EFFECTS = frozenset({
    EFFECT_SUBTITLE_STYLE, EFFECT_LOGO_OVERLAY, EFFECT_ZOOM, EFFECT_MUSIC_MIX,
    EFFECT_CTA_OVERLAY,
})
