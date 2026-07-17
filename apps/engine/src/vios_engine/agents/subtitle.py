"""Subtitle Agent (M8): transcript literal → track subtitle sobre la IR ya cortada.

Determinista, sin LLM. Texto = transcript LITERAL (anti-alucinación: tramos
low_confidence se marcan, nunca se corrigen). Todo el estilo de subtítulo lo
aplica ESTE agente (BrandingAgent no toca el track subtitle).
Política de cortes: una palabra cuyo intervalo no cabe entero en el clip de
vídeo se OMITE — nunca mostrar texto cuyo audio ya no existe en la timeline.
"""
from __future__ import annotations

from dataclasses import dataclass

from vios_contracts import (
    EFFECT_SUBTITLE_STYLE,
    ClientProfile,
    MediaIntelligence,
    Playbook,
    SubtitlePolicy,
    TimelineDraft,
    TimelineIR,
    s_to_frames,
    source_frame_to_timeline,
)
from vios_contracts.client_profile import SubtitleStyle
from vios_contracts.timeline_ir import Clip

from .layout import SUBTITLE_MAX_LINE_CHARS, SUBTITLE_POSITION_DEFAULT
from .qa import normalize as qa_normalize

AGENT_NAME = "subtitle-agent"


@dataclass
class _Entry:
    """Clip de subtítulo pendiente: texto literal + rango en frames de source."""
    asset_id: str
    text: str
    start_f: int
    end_f: int
    low_confidence: bool


class SubtitleAgent:
    def add_subtitles(
        self,
        ir: TimelineIR,
        intel_by_asset: dict[str, MediaIntelligence],
        playbook: Playbook,
        profile: ClientProfile,
        constraints=None,
    ) -> TimelineIR:
        """Añade el track subtitle como nueva revisión auditada de la IR."""
        policy = playbook.subtitles or SubtitlePolicy()
        draft = TimelineDraft.from_ir(ir)
        if not policy.enabled:
            return draft.commit(by=AGENT_NAME,
                                why="subtítulos desactivados por playbook",
                                action="skip")

        entries = self._collect_entries(ir, intel_by_asset, policy)
        if not entries:
            return draft.commit(by=AGENT_NAME,
                                why="transcript vacío o sin palabras visibles tras la edición",
                                action="skip")

        style = profile.visual.subtitle_style if profile.visual else None
        uppercase = policy.uppercase or bool(style and style.uppercase)
        banned = constraints.banned_subtitle_texts if constraints else set()
        vetoed = 0
        low_count = 0
        tid = draft.add_track("subtitle")
        for entry, t_start in entries:
            if banned and qa_normalize(entry.text) in banned:
                vetoed += 1
                continue
            duration = entry.end_f - entry.start_f
            text = entry.text.upper() if uppercase else entry.text
            cid = draft.add_clip(tid, source=text, start=t_start,
                                 in_point=0, out_point=duration)
            draft.add_clip_effect(tid, cid, self._style_effect(style, policy, entry))
            low_count += int(entry.low_confidence)

        mode = "karaoke" if policy.karaoke else "líneas"
        veto_note = f", {vetoed} vetados por QA" if vetoed else ""
        return draft.commit(
            by=AGENT_NAME,
            why=f"subtítulos {mode} literales del transcript "
                f"({len(entries) - vetoed} clips, {low_count} low_confidence"
                f"{veto_note})",
            action="add_subtitles",
        )

    # --- construcción de entradas (frames de source + remapeo a timeline) ---

    def _collect_entries(
        self,
        ir: TimelineIR,
        intel_by_asset: dict[str, MediaIntelligence],
        policy: SubtitlePolicy,
    ) -> list[tuple[_Entry, int]]:
        out: list[tuple[_Entry, int]] = []
        for track in ir.tracks:
            if track.kind != "video":
                continue
            for clip in track.clips:
                intel = intel_by_asset.get(clip.source)
                if intel is None:
                    continue
                for seg in intel.transcript.segments:
                    out.extend(self._entries_for_segment(ir, clip, seg, policy))
        return sorted(out, key=lambda pair: pair[1])

    def _entries_for_segment(self, ir, clip: Clip, seg, policy) -> list[tuple[_Entry, int]]:
        fps = ir.fps
        visible = [
            (w, s_to_frames(w.start_s, fps), s_to_frames(w.end_s, fps))
            for w in seg.words
            if clip.in_point <= s_to_frames(w.start_s, fps)
            and s_to_frames(w.end_s, fps) <= clip.out_point
        ]
        entries: list[_Entry] = []
        if visible and policy.karaoke:
            entries = [_Entry(clip.source, w.text, sf, ef, seg.low_confidence)
                       for w, sf, ef in visible]
        elif visible:
            entries = self._group_lines(clip.source, visible, seg.low_confidence)
        elif not seg.words:
            # segmento sin word-timing: clamp del rango del segmento al clip
            sf = max(s_to_frames(seg.start_s, fps), clip.in_point)
            ef = min(s_to_frames(seg.end_s, fps), clip.out_point)
            if ef > sf:
                entries = [_Entry(clip.source, seg.text, sf, ef, seg.low_confidence)]

        placed: list[tuple[_Entry, int]] = []
        for e in entries:
            if e.end_f <= e.start_f:
                continue
            t_start = source_frame_to_timeline(ir, e.asset_id, e.start_f)
            if t_start is not None:
                placed.append((e, t_start))
        return placed

    def _group_lines(self, asset_id: str, visible, low_confidence: bool) -> list[_Entry]:
        entries: list[_Entry] = []
        line: list[tuple] = []

        def flush():
            if line:
                text = " ".join(w.text for w, _, _ in line)
                entries.append(_Entry(asset_id, text, line[0][1], line[-1][2],
                                      low_confidence))

        for item in visible:
            candidate = " ".join(w.text for w, _, _ in [*line, item])
            if line and len(candidate) > SUBTITLE_MAX_LINE_CHARS:
                flush()
                line = [item]
            else:
                line.append(item)
        flush()
        return entries

    # --- estilo (responsabilidad única de este agente) ---

    def _style_effect(self, style: SubtitleStyle | None, policy: SubtitlePolicy,
                      entry: _Entry) -> dict:
        return {
            "type": EFFECT_SUBTITLE_STYLE,
            "params": {
                "font": style.font if style else "",
                "size_rel": style.size_rel if style else 1.0,
                "color_base": style.color_base if style else "",
                "color_emphasis": style.color_emphasis if style else "",
                "position": (style.position if style else SUBTITLE_POSITION_DEFAULT),
                "uppercase": policy.uppercase or bool(style and style.uppercase),
                "karaoke": policy.karaoke,
                "low_confidence": entry.low_confidence,
            },
        }
