"""B-Roll Agent (M10): b-roll EXISTENTE del cliente en los valles de voz.

Determinista, sin LLM. Anti-alucinación: solo assets reales de `library.broll`
con duración de su MediaIntelligence (sin análisis → se descarta anotado, nunca
se inventa). Los valles son el complemento de los rangos de voz, y SOLO dentro
de clips cuyo source tiene transcript (el outro o material sin habla no se
tapan). La ventana de hook queda protegida: ahí siempre se ve al speaker.
No bloqueante: sin biblioteca o sin valles no hay NEEDS_INPUT, hay skip.
"""
from __future__ import annotations

from vios_contracts import (
    ClientProfile,
    MediaIntelligence,
    Playbook,
    TimelineDraft,
    TimelineIR,
    s_to_frames,
    speech_ranges_in_timeline,
)

from .layout import BROLL_MIN_VALLEY_S, cover_scale

AGENT_NAME = "broll-agent"


class BRollAgent:
    def apply_broll(
        self,
        ir: TimelineIR,
        intel_by_asset: dict[str, MediaIntelligence],
        playbook: Playbook,
        profile: ClientProfile,
        constraints=None,
    ) -> TimelineIR:
        """Inserta b-roll en los valles como nueva revisión auditada de la IR."""
        draft = TimelineDraft.from_ir(ir)
        assets = profile.library.broll if profile.library else []
        if not assets:
            return draft.commit(by=AGENT_NAME,
                                why="sin b-roll en la biblioteca del cliente",
                                action="skip")

        banned = constraints.banned_assets if constraints else set()
        usable, discarded, vetoed = [], [], []
        for asset in assets:
            if asset.url in banned:
                vetoed.append(asset.url)
                continue
            intel = intel_by_asset.get(asset.url)
            if intel is None or intel.duration_s is None:
                discarded.append(asset.url)
            else:
                usable.append((asset, intel))
        if not usable:
            why = f"b-roll sin análisis (duración desconocida): {discarded}"
            if vetoed:
                why += f"; vetados por QA: {vetoed}"
            return draft.commit(by=AGENT_NAME, why=why, action="skip")

        valleys = self._valleys(ir, intel_by_asset, playbook)
        if not valleys:
            why = "sin valles de voz donde insertar b-roll"
            if discarded:
                why += f"; sin análisis: {discarded}"
            return draft.commit(by=AGENT_NAME, why=why, action="skip")

        notes: list[str] = []
        if vetoed:
            notes.append(f"vetados por QA: {vetoed}")
        if discarded:
            notes.append(f"sin análisis (descartados): {discarded}")
        track_id = draft.add_track("video")
        no_dims: set[str] = set()
        placed = 0
        for i, (start, end) in enumerate(valleys):
            asset, intel = usable[i % len(usable)]
            frames = min(s_to_frames(intel.duration_s, ir.fps), end - start)
            transform = None
            if intel.width is not None and intel.height is not None:
                scale = cover_scale(ir.canvas.width, ir.canvas.height,
                                    intel.width, intel.height)
                if abs(scale - 1.0) > 1e-9:
                    transform = {"scale": scale}
            else:
                no_dims.add(asset.url)
            draft.add_clip(track_id, source=asset.url, start=start,
                           in_point=0, out_point=frames, transform=transform)
            placed += 1
        if no_dims:
            notes.append(f"sin dimensiones (sin reframe): {sorted(no_dims)}")

        notes.insert(0, f"{placed} clips de b-roll en valles "
                        f"{[(s, e) for s, e in valleys]}")
        return draft.commit(by=AGENT_NAME, why="b-roll: " + "; ".join(notes),
                            action="apply_broll")

    def _valleys(
        self,
        ir: TimelineIR,
        intel_by_asset: dict[str, MediaIntelligence],
        playbook: Playbook,
    ) -> list[tuple[int, int]]:
        """Huecos sin voz ≥ mínimo, dentro de clips con transcript, fuera del hook."""
        speech = speech_ranges_in_timeline(ir, intel_by_asset)
        min_frames = s_to_frames(BROLL_MIN_VALLEY_S, ir.fps)
        hook_end = (s_to_frames(playbook.hook.max_seconds, ir.fps)
                    if playbook.hook else 0)
        valleys: list[tuple[int, int]] = []
        for track in ir.tracks:
            if track.kind != "video":
                continue
            for clip in track.clips:
                intel = intel_by_asset.get(clip.source)
                if intel is None or not intel.transcript.segments:
                    continue                    # material que no entendemos: no se tapa
                span_start = clip.start
                span_end = clip.start + (clip.out_point - clip.in_point)
                cursor = span_start
                for s, e in speech:
                    if e <= span_start or s >= span_end:
                        continue
                    if s > cursor:
                        valleys.append((cursor, min(s, span_end)))
                    cursor = max(cursor, e)
                if cursor < span_end:
                    valleys.append((cursor, span_end))
        trimmed = [(max(s, hook_end), e) for s, e in valleys]
        return sorted((s, e) for s, e in trimmed if e - s >= min_frames)
