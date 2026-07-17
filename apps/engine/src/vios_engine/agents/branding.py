"""Branding Agent (M8): logo + intro/outro del cliente sobre la IR ya cortada.

Determinista, sin LLM. Solo usa assets reales de la ficha (anti-alucinación):
la duración del intro/outro sale de su MediaIntelligence, nunca se inventa —
si falta y el asset es mandatory → NEEDS_INPUT explícito. No toca el track
subtitle (el estilo de subtítulos es responsabilidad del SubtitleAgent).
"""
from __future__ import annotations

from vios_contracts import (
    EFFECT_LOGO_OVERLAY,
    ClientProfile,
    MediaIntelligence,
    Playbook,
    TimelineDraft,
    TimelineIR,
    s_to_frames,
)

from .layout import LOGO_CORNER_DEFAULT, LOGO_MARGIN_REL

AGENT_NAME = "branding-agent"


class BrandingAgent:
    def apply_branding(
        self,
        ir: TimelineIR,
        profile: ClientProfile,
        playbook: Playbook,
        intel_by_asset: dict[str, MediaIntelligence] | None = None,
    ) -> TimelineIR:
        """Aplica branding como nueva revisión auditada de la IR."""
        intel_by_asset = intel_by_asset or {}
        visual = profile.visual
        draft = TimelineDraft.from_ir(ir)
        notes: list[str] = []

        outro_frames = self._resolve_outro_frames(ir, profile, intel_by_asset, notes)
        end = _timeline_end(ir)
        if outro_frames:
            video_track = next((t for t in ir.tracks if t.kind == "video"), None)
            if video_track is None:
                raise ValueError("IR sin track de vídeo: no hay dónde colocar el outro")
            draft.add_clip(video_track.id, source=visual.intro_outro.file,
                           start=end, in_point=0, out_point=outro_frames)
            end += outro_frames
            notes.append(f"outro '{visual.intro_outro.file}' ({outro_frames}f)")

        logos = visual.logos if visual else []
        if logos and end > 0:
            logo = logos[0]
            gid = draft.add_track("graphic")
            cid = draft.add_clip(gid, source=logo.file or logo.name,
                                 start=0, in_point=0, out_point=end)
            draft.add_clip_effect(gid, cid, {
                "type": EFFECT_LOGO_OVERLAY,
                "params": {"file": logo.file, "corner": LOGO_CORNER_DEFAULT,
                           "margin_rel": LOGO_MARGIN_REL},
            })
            notes.append(f"logo '{logo.name}' {LOGO_CORNER_DEFAULT}")
        else:
            notes.append("sin logo en la ficha")

        return draft.commit(
            by=AGENT_NAME,
            why="branding: " + "; ".join(notes),
            action="apply_branding",
        )

    def _resolve_outro_frames(
        self,
        ir: TimelineIR,
        profile: ClientProfile,
        intel_by_asset: dict[str, MediaIntelligence],
        notes: list[str],
    ) -> int:
        """Frames del intro/outro con duración REAL, o 0 si no aplica.

        v1: el archivo único de la ficha se materializa como OUTRO al final
        (la ficha no distingue intro de outro; ver doc M8 §11).
        """
        io = profile.visual.intro_outro if profile.visual else None
        if io is None or not io.exists:
            return 0
        if not io.file:
            if io.mandatory:
                raise ValueError(
                    "NEEDS_INPUT: intro_outro.mandatory=true pero la ficha no tiene file"
                )
            notes.append("intro/outro sin file (no mandatory): omitido")
            return 0
        intel = intel_by_asset.get(io.file)
        duration_s = intel.duration_s if intel else None
        if duration_s is None:
            if io.mandatory:
                raise ValueError(
                    f"NEEDS_INPUT: falta la duración real (MediaIntelligence) del "
                    f"intro/outro '{io.file}' — no se inventa"
                )
            notes.append(f"intro/outro '{io.file}' sin análisis: omitido")
            return 0
        return s_to_frames(duration_s, ir.fps)


def _timeline_end(ir: TimelineIR) -> int:
    """Último frame ocupado por cualquier clip de la timeline."""
    ends = [c.start + (c.out_point - c.in_point) for t in ir.tracks for c in t.clips]
    return max(ends, default=0)
