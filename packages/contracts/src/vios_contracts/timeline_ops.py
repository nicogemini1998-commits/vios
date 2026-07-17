"""Operaciones puras sobre Timeline IR: validate, diff, serialización, export schema."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .timeline_ir import TimelineIR


class TimelineValidationError(ValueError):
    """La IR viola una regla semántica (más allá de los tipos de Pydantic)."""


def validate(ir: TimelineIR) -> None:
    """Valida semántica (RF5). Los tipos ya los garantiza Pydantic. Lanza en error."""
    if ir.fps <= 0:
        raise TimelineValidationError("fps debe ser > 0")
    if ir.canvas.width <= 0 or ir.canvas.height <= 0:
        raise TimelineValidationError("canvas width/height deben ser > 0")
    if ir.revision < 0:
        raise TimelineValidationError("revision no puede ser negativa")
    if ir.parent_revision is not None and ir.parent_revision >= ir.revision:
        raise TimelineValidationError("parent_revision debe ser < revision")

    track_ids: set[str] = set()
    clip_ids: set[str] = set()
    for track in ir.tracks:
        if track.id in track_ids:
            raise TimelineValidationError(f"track id duplicado: {track.id}")
        track_ids.add(track.id)
        for clip in track.clips:
            if clip.id in clip_ids:
                raise TimelineValidationError(f"clip id duplicado: {clip.id}")
            clip_ids.add(clip.id)
            if clip.start < 0 or clip.in_point < 0 or clip.out_point < 0:
                raise TimelineValidationError(f"frames negativos en clip {clip.id}")
            if clip.out_point <= clip.in_point:
                raise TimelineValidationError(
                    f"clip {clip.id}: out_point ({clip.out_point}) <= in_point ({clip.in_point})"
                )

    marker_ids: set[str] = set()
    for marker in ir.markers:
        if marker.id in marker_ids:
            raise TimelineValidationError(f"marker id duplicado: {marker.id}")
        marker_ids.add(marker.id)
        if marker.at < 0:
            raise TimelineValidationError(f"marker {marker.id}: 'at' negativo")


def s_to_frames(seconds: float, fps: int) -> int:
    """Conversión canónica segundos → frames. ÚNICA aritmética de fps permitida."""
    if fps <= 0:
        raise ValueError(f"fps debe ser > 0, recibido {fps}")
    return round(seconds * fps)


def frames_to_s(frames: int, fps: int) -> float:
    """Conversión canónica frames → segundos (inversa de s_to_frames)."""
    if fps <= 0:
        raise ValueError(f"fps debe ser > 0, recibido {fps}")
    return frames / fps


def source_frame_to_timeline(ir: TimelineIR, asset_id: str, source_frame: int) -> int | None:
    """Remapea un frame del SOURCE al frame de timeline donde quedó tras la edición.

    Busca en tracks de vídeo el clip de ese asset cuyo rango [in_point, out_point)
    contiene el frame. None si ese instante fue cortado (no está en la timeline).
    Compartido por las capas F4 (subtítulos, ducking, b-roll).
    """
    for track in ir.tracks:
        if track.kind != "video":
            continue
        for clip in track.clips:
            if clip.source == asset_id and clip.in_point <= source_frame < clip.out_point:
                return clip.start + (source_frame - clip.in_point)
    return None


class Change(BaseModel):
    op: str            # add | remove | modify
    path: str          # ej. tracks/v0, tracks/v0/clips/c0, markers/m0
    before: Any = None
    after: Any = None


def _index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {it["id"]: it for it in items}


def diff(ir_a: TimelineIR, ir_b: TimelineIR) -> list[Change]:
    """Diff estructural determinista entre dos revisiones (RF6)."""
    changes: list[Change] = []
    a = ir_a.model_dump(mode="json")
    b = ir_b.model_dump(mode="json")

    ta, tb = _index(a["tracks"]), _index(b["tracks"])
    for tid in sorted(set(ta) | set(tb)):
        if tid not in ta:
            changes.append(Change(op="add", path=f"tracks/{tid}", after=tb[tid]))
            continue
        if tid not in tb:
            changes.append(Change(op="remove", path=f"tracks/{tid}", before=ta[tid]))
            continue
        ca, cb = _index(ta[tid]["clips"]), _index(tb[tid]["clips"])
        for cid in sorted(set(ca) | set(cb)):
            path = f"tracks/{tid}/clips/{cid}"
            if cid not in ca:
                changes.append(Change(op="add", path=path, after=cb[cid]))
            elif cid not in cb:
                changes.append(Change(op="remove", path=path, before=ca[cid]))
            elif ca[cid] != cb[cid]:
                changes.append(Change(op="modify", path=path, before=ca[cid], after=cb[cid]))

    ma, mb = _index(a["markers"]), _index(b["markers"])
    for mid in sorted(set(ma) | set(mb)):
        path = f"markers/{mid}"
        if mid not in ma:
            changes.append(Change(op="add", path=path, after=mb[mid]))
        elif mid not in mb:
            changes.append(Change(op="remove", path=path, before=ma[mid]))
        elif ma[mid] != mb[mid]:
            changes.append(Change(op="modify", path=path, before=ma[mid], after=mb[mid]))

    return changes


def to_json(ir: TimelineIR) -> str:
    """Serialización canónica con claves ordenadas (diffs estables) (RF7)."""
    return json.dumps(ir.model_dump(mode="json"), sort_keys=True, indent=2, ensure_ascii=False)


def from_json(s: str) -> TimelineIR:
    return TimelineIR.model_validate(json.loads(s))


def export_json_schema(path: str | Path) -> None:
    """Exporta el JSON Schema de la IR para consumidores no-Python (RF8)."""
    schema = TimelineIR.model_json_schema()
    Path(path).write_text(
        json.dumps(schema, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
