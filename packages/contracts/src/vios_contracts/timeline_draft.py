"""TimelineDraft — builder mutable. Único camino para cambiar una IR.

Trabaja sobre un dict (copia profunda del dump de la IR base); `commit` valida,
sube la revisión, enlaza parent y anota una Decision. La IR base nunca muta (RF3).
"""
from __future__ import annotations

import copy
from typing import Any

from .timeline_ir import TimelineIR, kind_prefix
from .timeline_ops import validate


class TimelineDraft:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @classmethod
    def from_ir(cls, ir: TimelineIR) -> TimelineDraft:
        return cls(copy.deepcopy(ir.model_dump()))

    # --- ids deterministas ---
    def _next_id(self, prefix: str) -> str:
        seq: dict[str, int] = self._data["id_seq"]
        idx = seq.get(prefix, 0)
        seq[prefix] = idx + 1
        return f"{prefix}{idx}"

    # --- mutadores ---
    def add_track(self, kind: str) -> str:
        tid = self._next_id(kind_prefix(kind))
        self._data["tracks"].append({"id": tid, "kind": kind, "clips": []})
        return tid

    def add_clip(
        self,
        track_id: str,
        source: str,
        start: int,
        in_point: int,
        out_point: int,
        transform: dict[str, Any] | None = None,
        effects: list[dict[str, Any]] | None = None,
    ) -> str:
        track = self._find_track(track_id)
        cid = self._next_id("c")
        clip: dict[str, Any] = {
            "id": cid,
            "source": source,
            "start": start,
            "in_point": in_point,
            "out_point": out_point,
            "effects": effects or [],
        }
        if transform is not None:
            clip["transform"] = transform
        track["clips"].append(clip)
        return cid

    def add_marker(
        self,
        kind: str,
        at: int,
        label: str = "",
        payload: dict[str, Any] | None = None,
    ) -> str:
        mid = self._next_id("m")
        self._data["markers"].append(
            {"id": mid, "kind": kind, "at": at, "label": label, "payload": payload or {}}
        )
        return mid

    def add_clip_effect(self, track_id: str, clip_id: str, effect: dict[str, Any]) -> None:
        """Añade un effect (append) a un clip existente. KeyError si no existe."""
        clip = self._find_clip(track_id, clip_id)
        clip.setdefault("effects", []).append(effect)

    def set_clip_transform(self, track_id: str, clip_id: str, transform: dict[str, Any]) -> None:
        """Reemplaza el transform de un clip existente. KeyError si no existe."""
        clip = self._find_clip(track_id, clip_id)
        clip["transform"] = transform

    def remove_track(self, track_id: str) -> None:
        self._data["tracks"] = [t for t in self._data["tracks"] if t["id"] != track_id]

    def remove_clip(self, track_id: str, clip_id: str) -> None:
        track = self._find_track(track_id)
        track["clips"] = [c for c in track["clips"] if c["id"] != clip_id]

    def remove_marker(self, marker_id: str) -> None:
        self._data["markers"] = [m for m in self._data["markers"] if m["id"] != marker_id]

    def _find_clip(self, track_id: str, clip_id: str) -> dict[str, Any]:
        track = self._find_track(track_id)
        for c in track["clips"]:
            if c["id"] == clip_id:
                return c
        raise KeyError(f"clip no encontrado: {clip_id} (track {track_id})")

    def _find_track(self, track_id: str) -> dict[str, Any]:
        for t in self._data["tracks"]:
            if t["id"] == track_id:
                return t
        raise KeyError(f"track no encontrado: {track_id}")

    # --- commit ---
    def commit(self, by: str, why: str, action: str = "") -> TimelineIR:
        """Produce una NUEVA IR inmutable: revision+1, parent enlazado, Decision anotada."""
        base_rev = self._data["revision"]
        new_rev = base_rev + 1
        self._data["parent_revision"] = base_rev
        self._data["revision"] = new_rev
        self._data["meta"]["decisions"].append(
            {"revision": new_rev, "agent": by, "why": why, "action": action}
        )
        ir = TimelineIR.model_validate(self._data)
        validate(ir)
        return ir
