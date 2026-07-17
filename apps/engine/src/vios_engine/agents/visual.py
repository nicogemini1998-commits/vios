"""Visual/Motion Agent (M9): reframe al canvas + zooms de ritmo sobre la IR cortada.

Determinista, sin LLM. El reframe usa dimensiones REALES del source
(MediaIntelligence); sin dimensiones no se escala a ciegas, se anota. Los zooms
siguen una regla fija auditable (beats alternados, intensidad por cut_style),
sin criterio estético inventado. No toca tracks subtitle/graphic/audio.
"""
from __future__ import annotations

from vios_contracts import (
    EFFECT_ZOOM,
    ClientProfile,
    MediaIntelligence,
    Playbook,
    TimelineDraft,
    TimelineIR,
)

from .layout import ZOOM_INTENSITY, cover_scale

AGENT_NAME = "visual-agent"


class VisualMotionAgent:
    def apply_motion(
        self,
        ir: TimelineIR,
        intel_by_asset: dict[str, MediaIntelligence],
        playbook: Playbook,
        profile: ClientProfile,
    ) -> TimelineIR:
        """Aplica reframe + zooms como nueva revisión auditada de la IR."""
        draft = TimelineDraft.from_ir(ir)
        notes: list[str] = []
        reframed = self._reframe(ir, intel_by_asset, draft, notes)
        zoomed = self._zooms(ir, playbook, profile, draft)

        notes.insert(0, f"{reframed} reframes, {zoomed} zooms")
        return draft.commit(by=AGENT_NAME, why="motion: " + "; ".join(notes),
                            action="apply_motion")

    def _reframe(self, ir, intel_by_asset, draft, notes) -> int:
        canvas = ir.canvas
        missing: set[str] = set()
        count = 0
        for track in ir.tracks:
            if track.kind != "video":
                continue
            for clip in track.clips:
                intel = intel_by_asset.get(clip.source)
                if intel is None or intel.width is None or intel.height is None:
                    missing.add(clip.source)
                    continue
                scale = cover_scale(canvas.width, canvas.height,
                                    intel.width, intel.height)
                if abs(scale - 1.0) < 1e-9:
                    continue
                draft.set_clip_transform(track.id, clip.id, {"scale": scale})
                count += 1
        if missing:
            notes.append(f"sin dimensiones (reframe omitido): {sorted(missing)}")
        return count

    def _zooms(self, ir, playbook, profile, draft) -> int:
        pacing = playbook.pacing
        client_pacing = profile.edit_rules.pacing if profile.edit_rules else None
        enabled = bool(pacing and pacing.zoom) or bool(client_pacing and client_pacing.zooms)
        if not enabled:
            return 0
        cut_style = pacing.cut_style if pacing else "medium"
        delta = ZOOM_INTENSITY.get(cut_style, ZOOM_INTENSITY["medium"])
        beat_frames = {m.at for m in ir.markers if m.kind == "beat"}
        peak = round(1.0 + delta, 4)
        count = 0
        for track in ir.tracks:
            if track.kind != "video":
                continue
            for clip in track.clips:
                if clip.start not in beat_frames:
                    continue
                zoom_in = count % 2 == 0            # alternado, determinista
                params = ({"scale_from": 1.0, "scale_to": peak} if zoom_in
                          else {"scale_from": peak, "scale_to": 1.0})
                draft.add_clip_effect(track.id, clip.id,
                                      {"type": EFFECT_ZOOM, "params": params})
                count += 1
        return count
