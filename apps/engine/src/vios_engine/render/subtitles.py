"""Track subtitle → archivo ASS/SSA (burn-in con el filtro `ass`).

Fiel a M8: el texto de cada clip es el transcript LITERAL (líneas o palabra a
palabra en karaoke); el estilo sale de los params `subtitle_style` (hex/font
exactos de la ficha). Función pura: devuelve el contenido como string.
"""
from __future__ import annotations

from vios_contracts import EFFECT_SUBTITLE_STYLE, TimelineIR, frames_to_s

from .masters import SUBTITLE_FONT_SIZE_REL

_ALIGNMENT = {"bottom": 2, "top": 8, "middle": 5}


def _ass_time(seconds: float) -> str:
    cs = round(seconds * 100)
    h, rem = divmod(cs, 360_000)
    m, rem = divmod(rem, 6_000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def _ass_color(hex_color: str) -> str:
    """#RRGGBB → &H00BBGGRR (formato ASS, alpha 00 = opaco)."""
    if not hex_color:
        return "&H00FFFFFF"
    r, g, b = hex_color[1:3], hex_color[3:5], hex_color[5:7]
    return f"&H00{b}{g}{r}".upper()


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def build_ass(ir: TimelineIR) -> str | None:
    """Genera el ASS de todos los clips subtitle. None si no hay subtítulos."""
    clips = [c for t in ir.tracks if t.kind == "subtitle" for c in t.clips]
    if not clips:
        return None

    style = next((e.params for c in clips for e in c.effects
                  if e.type == EFFECT_SUBTITLE_STYLE), {})
    font = style.get("font") or "Arial"
    size = round(ir.canvas.height * SUBTITLE_FONT_SIZE_REL
                 * float(style.get("size_rel", 1.0)))
    base = _ass_color(style.get("color_base", ""))
    emphasis = _ass_color(style.get("color_emphasis", "") or style.get("color_base", ""))
    align = _ALIGNMENT.get(style.get("position", "bottom"), 2)
    karaoke = bool(style.get("karaoke", False))

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {ir.canvas.width}",
        f"PlayResY: {ir.canvas.height}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Alignment, MarginL, MarginR, "
        "MarginV, BorderStyle, Outline, Shadow",
        f"Style: Default,{font},{size},{base},{emphasis},&H00000000,&H80000000,"
        f"-1,0,{align},40,40,60,1,2,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for clip in sorted(clips, key=lambda c: c.start):
        start_s = frames_to_s(clip.start, ir.fps)
        dur_frames = clip.out_point - clip.in_point
        end_s = frames_to_s(clip.start + dur_frames, ir.fps)
        text = _escape(clip.source)
        if karaoke:
            dur_cs = round(frames_to_s(dur_frames, ir.fps) * 100)
            text = f"{{\\k{dur_cs}}}{text}"
        lines.append(
            f"Dialogue: 0,{_ass_time(start_s)},{_ass_time(end_s)},Default,,0,0,0,,{text}"
        )
    return "\n".join(lines) + "\n"
