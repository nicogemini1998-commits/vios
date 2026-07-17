"""Specs de render por dato (directiva Nico: añadir plataforma = añadir dato).

Como `agents/layout.py`: sin números mágicos dispersos por el código.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MasterSpec:
    width: int
    height: int
    fps: int
    video_bitrate: str
    audio_bitrate: str


PLATFORM_MASTERS: dict[str, MasterSpec] = {
    "instagram": MasterSpec(1080, 1920, 30, "10M", "192k"),
    "tiktok": MasterSpec(1080, 1920, 30, "10M", "192k"),
    "youtube": MasterSpec(1920, 1080, 30, "12M", "192k"),
}

MASTER_VIDEO_ARGS = ("-c:v", "libx264", "-profile:v", "high", "-preset", "medium",
                     "-pix_fmt", "yuv420p")
MASTER_AUDIO_ARGS = ("-c:a", "aac")

PREVIEW_HEIGHT = 480
PREVIEW_VIDEO_ARGS = ("-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                      "-pix_fmt", "yuv420p")
PREVIEW_AUDIO_ARGS = ("-c:a", "aac", "-b:a", "128k")

# ducking determinista sobre duck_ranges de la IR (decisión Nico M11 §4 d1, opción A)
DUCK_LEVEL_REL = 0.3      # nivel de la música bajo la voz, relativo a su volumen base
DUCK_ATTACK_S = 0.15      # rampa de entrada al valle (suave, no corte seco)
DUCK_RELEASE_S = 0.30     # rampa de salida

# tamaño del logo relativo al ancho del canvas (se calibra con el primer render real)
LOGO_WIDTH_REL = 0.15

# tipografía de subtítulos/CTA relativa a la altura del canvas
SUBTITLE_FONT_SIZE_REL = 0.045
# calibrado con el primer render real (MVP): 0.055 desbordaba el ancho 9:16
# con el CTA de 27 chars de la ficha Cliender
CTA_FONT_SIZE_REL = 0.034
CTA_Y_REL = 0.78          # dentro de la safe-area inferior sin pisar subtítulos
