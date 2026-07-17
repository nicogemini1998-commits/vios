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

KNOWN_EFFECTS = frozenset({EFFECT_SUBTITLE_STYLE, EFFECT_LOGO_OVERLAY})
