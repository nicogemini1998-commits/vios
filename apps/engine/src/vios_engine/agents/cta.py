"""CTA/Thumbnail Agent (M10): overlay de CTA + candidato de thumbnail en la IR.

Determinista, sin LLM. El copy sale SOLO de la ficha (`audience.cta`) o del
playbook (`cta.default_text`) — sin texto en ninguno no se inventa, se omite.
El thumbnail es una anotación (marker) con el frame candidato del SOURCE:
punto medio del mejor hook (ya scoreado por Story) o del primer clip; la
extracción real del frame llega con el render (F5).
"""
from __future__ import annotations

from vios_contracts import (
    EFFECT_CTA_OVERLAY,
    ClientProfile,
    Clip,
    CTAPolicy,
    Playbook,
    TimelineDraft,
    TimelineIR,
    s_to_frames,
    source_frame_to_timeline,
    timeline_end,
)

from .layout import CTA_DURATION_S

AGENT_NAME = "cta-agent"


class CTAThumbnailAgent:
    def apply_cta(
        self,
        ir: TimelineIR,
        playbook: Playbook,
        profile: ClientProfile,
        constraints=None,
    ) -> TimelineIR:
        """Añade CTA + thumbnail como nueva revisión auditada de la IR."""
        draft = TimelineDraft.from_ir(ir)
        end = timeline_end(ir)
        if end <= 0:
            return draft.commit(by=AGENT_NAME, why="timeline vacía", action="skip")

        notes: list[str] = []
        if constraints and constraints.drop_cta:
            notes.append("CTA vetado por QA: omitido")
            did_cta = False
        else:
            did_cta = self._cta_overlay(ir, playbook, profile, draft, end, notes)
        did_thumb = self._thumbnail(ir, draft, notes)
        return draft.commit(
            by=AGENT_NAME,
            why="cta/thumbnail: " + "; ".join(notes),
            action="apply_cta" if (did_cta or did_thumb) else "skip",
        )

    def _cta_overlay(self, ir, playbook, profile, draft, end, notes) -> bool:
        policy = playbook.cta or CTAPolicy()
        if not policy.enabled:
            notes.append("CTA desactivado por playbook")
            return False
        client_cta = profile.audience.cta if profile.audience else None
        text = (client_cta.text if client_cta and client_cta.text
                else policy.default_text)
        if not text:
            notes.append("sin copy de CTA (ficha y playbook vacíos): omitido")
            return False

        duration = min(s_to_frames(CTA_DURATION_S, ir.fps), end)
        marker = next((m for m in ir.markers if m.kind == "cta"), None)
        anchor = marker.at if marker else {
            "start": 0, "mid": end // 2,
        }.get(policy.position, end)
        start = max(0, min(anchor, end - duration))

        gid = draft.add_track("graphic")
        cid = draft.add_clip(gid, source=text, start=start,
                             in_point=0, out_point=duration)
        draft.add_clip_effect(gid, cid, {
            "type": EFFECT_CTA_OVERLAY,
            "params": {
                "text": text,
                "destination": client_cta.destination if client_cta else "",
                "position": policy.position,
                "font": self._cta_font(profile),
                "color": self._accent_color(profile),
            },
        })
        notes.append(f"CTA '{text}' en {start}-{start + duration}f")
        return True

    def _thumbnail(self, ir, draft, notes) -> bool:
        hook = next((m for m in ir.markers if m.kind == "hook"), None)
        if hook and {"asset_id", "start_s", "end_s"} <= hook.payload.keys():
            asset_id = hook.payload["asset_id"]
            mid_s = (hook.payload["start_s"] + hook.payload["end_s"]) / 2
            source_frame = s_to_frames(mid_s, ir.fps)
            origin = "punto medio del hook"
        else:
            clip = self._first_video_clip(ir)
            if clip is None:
                notes.append("sin clips de vídeo: sin thumbnail")
                return False
            asset_id = clip.source
            source_frame = (clip.in_point + clip.out_point) // 2
            origin = "punto medio del primer clip"
        at = self._to_timeline(ir, asset_id, source_frame)
        draft.add_marker("thumbnail", at=at, label=origin,
                         payload={"asset_id": asset_id, "source_frame": source_frame})
        notes.append(f"thumbnail: {origin} ({asset_id}@{source_frame})")
        return True

    def _first_video_clip(self, ir: TimelineIR) -> Clip | None:
        for track in ir.tracks:
            if track.kind == "video" and track.clips:
                return track.clips[0]
        return None

    def _to_timeline(self, ir: TimelineIR, asset_id: str, source_frame: int) -> int:
        at = source_frame_to_timeline(ir, asset_id, source_frame)
        return at if at is not None else 0

    def _cta_font(self, profile: ClientProfile) -> str:
        fonts = profile.visual.fonts if profile.visual else []
        return next((f.family for f in fonts if f.usage == "cta"), "")

    def _accent_color(self, profile: ClientProfile) -> str:
        palette = profile.visual.palette if profile.visual else []
        return next((c.hex for c in palette if c.role == "accent"), "")
