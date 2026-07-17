"""Audio/Music Agent (M9): música de la biblioteca real + ducking alineado a voz.

Determinista, sin LLM. Anti-alucinación: solo assets de `library.music_sfx`,
duración REAL de su MediaIntelligence (sin análisis → skip anotado, nunca se
inventa). Los rangos de ducking salen del transcript remapeado a la timeline.
La música no es bloqueante: sin biblioteca no hay NEEDS_INPUT, hay skip.
"""
from __future__ import annotations

from vios_contracts import (
    EFFECT_MUSIC_MIX,
    ClientProfile,
    MediaIntelligence,
    MusicPolicy,
    Playbook,
    TimelineDraft,
    TimelineIR,
    s_to_frames,
    speech_ranges_in_timeline,
    timeline_end,
)

AGENT_NAME = "audio-agent"


class AudioMusicAgent:
    def apply_music(
        self,
        ir: TimelineIR,
        intel_by_asset: dict[str, MediaIntelligence],
        playbook: Playbook,
        profile: ClientProfile,
        constraints=None,
    ) -> TimelineIR:
        """Añade el track de música como nueva revisión auditada de la IR."""
        policy = playbook.music or MusicPolicy()
        draft = TimelineDraft.from_ir(ir)
        if not policy.enabled:
            return draft.commit(by=AGENT_NAME, why="música desactivada por playbook",
                                action="skip")
        assets = profile.library.music_sfx if profile.library else []
        if not assets:
            return draft.commit(by=AGENT_NAME,
                                why="sin música en la biblioteca del cliente",
                                action="skip")
        music = assets[0]                       # v1: primer asset (determinista)
        if constraints and (constraints.drop_music
                            or music.url in constraints.banned_assets):
            return draft.commit(by=AGENT_NAME,
                                why=f"música '{music.url}' vetada por QA",
                                action="skip")
        intel = intel_by_asset.get(music.url)
        duration_s = intel.duration_s if intel else None
        if duration_s is None:
            return draft.commit(
                by=AGENT_NAME,
                why=f"música '{music.url}' sin análisis (duración desconocida): "
                    "no se inventa",
                action="skip")
        end = timeline_end(ir)
        if end <= 0:
            return draft.commit(by=AGENT_NAME, why="timeline vacía", action="skip")

        music_frames = min(s_to_frames(duration_s, ir.fps), end)
        duck_ranges = (speech_ranges_in_timeline(ir, intel_by_asset)
                       if policy.ducking else [])
        rules = profile.edit_rules.music if profile.edit_rules else None

        tid = draft.add_track("audio")
        cid = draft.add_clip(tid, source=music.url, start=0,
                             in_point=0, out_point=music_frames)
        draft.add_clip_effect(tid, cid, {
            "type": EFFECT_MUSIC_MIX,
            "params": {
                "volume_rel": rules.volume_rel if rules else 1.0,
                "target_lufs": policy.target_lufs,
                "ducking": policy.ducking,
                "duck_ranges": [{"start": s, "end": e} for s, e in duck_ranges],
            },
        })
        short = " (más corta que la pieza)" if music_frames < end else ""
        return draft.commit(
            by=AGENT_NAME,
            why=f"música '{music.url}' ({music_frames}f{short}), "
                f"ducking {len(duck_ranges)} rangos de voz",
            action="apply_music")
