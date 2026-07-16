"""ClientProfile — ficha de conocimiento del cliente (manual VIOS §5, bloques A-H).

Bloques A-F obligatorios, G-H opcionales. El tipo permite perfiles incompletos;
la obligatoriedad la impone `client_missing_blocks` (base del gate NEEDS_INPUT).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


# --- primitivos ---
class ColorToken(_Model):
    name: str
    hex: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")  # exacto, nunca aproximado (manual §2)
    role: str  # primary | secondary | accent | bg | text


class FontRef(_Model):
    family: str
    usage: str = ""            # titulos | cuerpo | subtitulos | cta
    weights: list[str] = Field(default_factory=list)
    license: str = ""


class LogoRef(_Model):
    name: str
    file: str = ""
    usage: str = ""


class SubtitleStyle(_Model):
    font: str = ""
    size_rel: float = 1.0
    color_base: str = ""
    color_emphasis: str = ""
    position: str = "bottom"
    uppercase: bool = False
    emojis: bool = False


class IntroOutro(_Model):
    exists: bool = False
    file: str = ""
    mandatory: bool = False


class Moodboard(_Model):
    likes: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)


class Blacklist(_Model):
    words: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)


class Target(_Model):
    age: str = ""
    profile: str = ""
    pain: str = ""
    scroll_stopper: str = ""


class CTA(_Model):
    text: str
    destination: str = ""


class MusicRules(_Model):
    style: str = ""
    library: list[str] = Field(default_factory=list)
    volume_rel: float = 1.0


class Pacing(_Model):
    aggressive_cuts: bool = False
    zooms: bool = False
    trend_aesthetic: bool = False


class Person(_Model):
    name: str
    release_signed: bool = False


class Asset(_Model):
    url: str
    description: str = ""


# --- bloques A-H ---
class Identity(_Model):        # A
    name: str
    slug: str
    legal_name: str = ""
    sector: str = ""
    location: str = ""
    web: str = ""
    socials: dict[str, str] = Field(default_factory=dict)
    description: list[str] = Field(default_factory=list)


class VisualIdentity(_Model):  # B
    logos: list[LogoRef] = Field(default_factory=list)
    palette: list[ColorToken] = Field(default_factory=list)
    fonts: list[FontRef] = Field(default_factory=list)
    subtitle_style: SubtitleStyle | None = None
    intro_outro: IntroOutro | None = None
    moodboard: Moodboard | None = None


class Voice(_Model):           # C
    tone: list[str] = Field(default_factory=list)
    treatment: Literal["tu", "usted"] = "tu"
    languages: list[str] = Field(default_factory=list)
    approved_phrases: list[str] = Field(default_factory=list)
    blacklist: Blacklist | None = None
    verified_data: list[str] = Field(default_factory=list)


class Audience(_Model):        # D
    target: Target | None = None
    default_goal: str = ""
    cta: CTA | None = None
    platforms: list[str] = Field(default_factory=list)


class EditRules(_Model):       # E
    authorized_playbooks: list[str] = Field(default_factory=list)
    default_playbook: str = ""
    durations: dict[str, str] = Field(default_factory=dict)
    pacing: Pacing | None = None
    music: MusicRules | None = None
    never_do: list[str] = Field(default_factory=list)
    authorized_people: list[Person] = Field(default_factory=list)


class Library(_Model):         # F
    broll: list[Asset] = Field(default_factory=list)
    brand_photos: list[Asset] = Field(default_factory=list)
    prior_approved: list[str] = Field(default_factory=list)
    prior_rejected: list[str] = Field(default_factory=list)
    music_sfx: list[Asset] = Field(default_factory=list)


class Commercial(_Model):      # G (opcional)
    services: list[str] = Field(default_factory=list)
    active_offers: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    account_manager: str = ""
    approval_channel: str = ""


class Learning(_Model):        # H (opcional, se rellena con el uso)
    numeric_goals: dict[str, float] = Field(default_factory=dict)
    performance_history: list[dict] = Field(default_factory=list)
    learned_adjustments: list[str] = Field(default_factory=list)


class ClientProfile(_Model):
    schema_version: str = SCHEMA_VERSION
    client_id: str
    name: str
    identity: Identity | None = None
    visual: VisualIdentity | None = None
    voice: Voice | None = None
    audience: Audience | None = None
    edit_rules: EditRules | None = None
    library: Library | None = None
    commercial: Commercial | None = None
    learning: Learning | None = None


def client_missing_blocks(p: ClientProfile) -> list[str]:
    """Bloques A-F ausentes o con campos críticos vacíos (manual §5). Vacío = editable."""
    missing: list[str] = []
    if p.identity is None or not p.identity.description:
        missing.append("A.identity: falta descripcion")
    if p.visual is None or not p.visual.palette or not p.visual.fonts:
        missing.append("B.visual: falta palette/fonts")
    if p.voice is None or not p.voice.tone or p.voice.blacklist is None:
        missing.append("C.voice: falta tono/blacklist")
    if p.audience is None or p.audience.cta is None or not p.audience.platforms:
        missing.append("D.audience: falta cta/plataformas")
    if p.edit_rules is None or not p.edit_rules.default_playbook:
        missing.append("E.edit_rules: falta default_playbook")
    if p.library is None:
        missing.append("F.library: bloque ausente")
    return missing


def is_client_editable(p: ClientProfile) -> bool:
    """True si la ficha A-F está completa → VIOS puede editar para este cliente."""
    return not client_missing_blocks(p)
