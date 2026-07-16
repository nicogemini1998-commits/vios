"""Muestreo de keyframes: 1 por escena (punto medio). Determinista, sin deps."""
from __future__ import annotations

from vios_contracts import Keyframe, Scene


class MidpointFrameSampler:
    def sample(self, scenes: list[Scene], duration_s: float | None = None) -> list[Keyframe]:
        frames: list[Keyframe] = []
        for sc in scenes:
            mid = (sc.start_s + sc.end_s) / 2.0
            frames.append(Keyframe(at_s=round(mid, 3), scene_index=sc.index))
        return frames
