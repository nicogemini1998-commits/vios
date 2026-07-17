"""Constantes de layout F4 — safe-areas y defaults, sin números mágicos dispersos.

Valores v1 para vertical social (9:16); se validarán con render real en F5.
"""
from __future__ import annotations

SUBTITLE_MAX_LINE_CHARS = 32
SUBTITLE_POSITION_DEFAULT = "bottom"

LOGO_CORNER_DEFAULT = "top_right"
LOGO_MARGIN_REL = 0.04

# intensidad de zoom por cut_style del playbook (M9)
ZOOM_INTENSITY = {"calm": 0.03, "medium": 0.05, "aggressive": 0.08}
