"""Edit Agent (M7): EditPlan → Timeline IR v1. Cortes reales, deterministas.

Reglas puras (sin LLM en v1): los momentos ya vienen decididos y justificados
por Director+Story; aquí se convierten a frames y se materializan como clips
consecutivos en un track de vídeo, con markers de beat/hook/cta.
Frontera de unidades: EditPlan en SEGUNDOS → IR en FRAMES (via fps).
"""
from __future__ import annotations

from vios_contracts import (
    Canvas,
    EditPlan,
    Playbook,
    TimelineDraft,
    TimelineIR,
    create_timeline,
    s_to_frames,
)

AGENT_NAME = "edit-agent"

# canvas por plataforma (v1: vertical social por defecto)
_PLATFORM_CANVAS: dict[str, Canvas] = {
    "instagram": Canvas(width=1080, height=1920, aspect="9:16"),
    "tiktok": Canvas(width=1080, height=1920, aspect="9:16"),
    "youtube": Canvas(width=1920, height=1080, aspect="16:9"),
}
_DEFAULT_CANVAS = Canvas(width=1080, height=1920, aspect="9:16")


class EditAgent:
    def __init__(self, fps: int = 30) -> None:
        self._fps = fps

    def build_timeline(self, plan: EditPlan, playbook: Playbook | None = None) -> TimelineIR:
        """Materializa el EditPlan como Timeline IR v1 (revisión 1, auditada)."""
        if not plan.moments:
            raise ValueError("EditPlan sin momentos: nada que editar")

        canvas = _PLATFORM_CANVAS.get(plan.platform, _DEFAULT_CANVAS)
        base = create_timeline(
            project_id=plan.project_id,
            fps=self._fps,
            canvas=canvas,
            platform=plan.platform,
            playbook=plan.playbook_id,
        )
        draft = TimelineDraft.from_ir(base)
        video_track = draft.add_track("video")
        audio_track = draft.add_track("audio")

        cursor = 0
        for m in sorted(plan.moments, key=lambda m: m.order):
            in_f = s_to_frames(m.start_s, self._fps)
            out_f = s_to_frames(m.end_s, self._fps)
            draft.add_clip(video_track, source=m.asset_id, start=cursor,
                           in_point=in_f, out_point=out_f)
            draft.add_clip(audio_track, source=m.asset_id, start=cursor,
                           in_point=in_f, out_point=out_f)
            draft.add_marker("beat", at=cursor, label=m.beat,
                             payload={"why": m.why, "order": m.order})
            cursor += out_f - in_f

        if plan.hooks:
            best = max(plan.hooks, key=lambda h: h.score)
            draft.add_marker("hook", at=0, label=best.text,
                             payload={"asset_id": best.asset_id,
                                      "start_s": best.start_s, "end_s": best.end_s,
                                      "score": best.score})

        cta = playbook.cta if playbook else None
        if cta is not None and cta.enabled:
            at = {"start": 0, "mid": cursor // 2}.get(cta.position, max(0, cursor - 1))
            draft.add_marker("cta", at=at, label=cta.default_text)

        return draft.commit(
            by=AGENT_NAME,
            why=f"EditPlan '{plan.intent}' → timeline v1 ({len(plan.moments)} momentos)",
            action="build_timeline",
        )
