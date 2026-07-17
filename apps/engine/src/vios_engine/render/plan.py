"""ir_to_filtergraph — función PURA: Timeline IR → plan de render ffmpeg.

Corazón testeable de M11 (golden tests sobre el texto del filtergraph ANTES de
ejecutar ffmpeg real). Sin I/O ni subprocess: los paths llegan resueltos en
`asset_paths` y el .ass se entrega como contenido (el runner lo materializa
sustituyendo el placeholder {ASS}).

Reglas: catálogo de effects CERRADO (desconocido → error); asset o font de la
ficha ausentes → error explícito con el nombre exacto (nunca render a ciegas).
"""
from __future__ import annotations

from dataclasses import dataclass

from vios_contracts import (
    EFFECT_CTA_OVERLAY,
    EFFECT_LOGO_OVERLAY,
    EFFECT_MUSIC_MIX,
    EFFECT_SUBTITLE_STYLE,
    EFFECT_ZOOM,
    KNOWN_EFFECTS,
    TimelineIR,
    frames_to_s,
    timeline_end,
)

from .masters import (
    CTA_FONT_SIZE_REL,
    CTA_Y_REL,
    DUCK_ATTACK_S,
    DUCK_LEVEL_REL,
    DUCK_RELEASE_S,
    LOGO_WIDTH_REL,
    MASTER_AUDIO_ARGS,
    MASTER_VIDEO_ARGS,
    PLATFORM_MASTERS,
    PREVIEW_AUDIO_ARGS,
    PREVIEW_HEIGHT,
    PREVIEW_VIDEO_ARGS,
)
from .subtitles import build_ass

ASS_PLACEHOLDER = "{ASS}"

_CORNERS = {
    "top_left": ("W*{m}", "H*{m}"),
    "top_right": ("W-w-W*{m}", "H*{m}"),
    "bottom_left": ("W*{m}", "H-h-H*{m}"),
    "bottom_right": ("W-w-W*{m}", "H-h-H*{m}"),
}


class RenderPlanError(ValueError):
    """La IR no se puede renderizar tal cual: falta un dato REAL o hay un effect desconocido."""


@dataclass(frozen=True)
class RenderPlan:
    inputs: tuple[tuple[str, ...], ...]     # tokens ffmpeg por input, en orden
    filter_complex: str
    video_label: str
    audio_label: str | None                 # None = sin audio (-an)
    output_args: tuple[str, ...]
    ass_content: str | None                 # el runner lo escribe y sustituye {ASS}


def _s(frames: int, fps: int) -> str:
    return f"{frames_to_s(frames, fps):.6f}"


def _num(value: float) -> str:
    return f"{value:.6f}"


def ir_to_filtergraph(
    ir: TimelineIR,
    asset_paths: dict[str, str],
    quality: str,
    platform: str,
    font_files: dict[str, str] | None = None,
) -> RenderPlan:
    if quality not in ("preview", "master"):
        raise RenderPlanError(f"quality desconocida: {quality}")
    if quality == "master" and platform not in PLATFORM_MASTERS:
        raise RenderPlanError(f"plataforma sin spec de master: {platform}")
    end = timeline_end(ir)
    if end <= 0:
        raise RenderPlanError("timeline vacía: nada que renderizar")
    _check_effects(ir)

    font_files = font_files or {}
    fps, cw, ch = ir.fps, ir.canvas.width, ir.canvas.height
    inputs: list[tuple[str, ...]] = []
    chains: list[str] = []

    def add_input(tokens: tuple[str, ...]) -> int:
        inputs.append(tokens)
        return len(inputs) - 1

    def path_of(source: str) -> str:
        if source not in asset_paths:
            raise RenderPlanError(f"asset sin path en storage: {source}")
        return asset_paths[source]

    video_tracks = [t for t in ir.tracks if t.kind == "video"]
    audio_tracks = [t for t in ir.tracks if t.kind == "audio"]
    graphic_clips = [c for t in ir.tracks if t.kind == "graphic" for c in t.clips]

    # --- base de vídeo: primer track de vídeo, o color si no hay (carrusel) ---
    if video_tracks and video_tracks[0].clips:
        labels = []
        for k, clip in enumerate(video_tracks[0].clips):
            idx = add_input(("-i", path_of(clip.source)))
            chains.append(_video_clip_chain(clip, idx, k, fps, cw, ch))
            labels.append(f"[bv{k}]")
        if len(labels) == 1:
            chains.append(f"{labels[0]}null[vbase]")
        else:
            chains.append(f"{''.join(labels)}concat=n={len(labels)}:v=1:a=0[vbase]")
    else:
        chains.append(f"color=c=black:s={cw}x{ch}:r={fps}:d={_s(end, fps)}[vbase]")
    vlabel = "[vbase]"

    # --- overlays de vídeo (b-roll, tracks de vídeo posteriores) ---
    step = 0
    for track in video_tracks[1:]:
        for clip in track.clips:
            idx = add_input(("-i", path_of(clip.source)))
            chains.append(_video_clip_chain(clip, idx, f"o{step}", fps, cw, ch,
                                            shift_start=True))
            out = f"[vov{step}]"
            chains.append(f"{vlabel}[bvo{step}]overlay=x=0:y=0:eof_action=pass{out}")
            vlabel = out
            step += 1

    # --- graphics: logo (imagen) y CTA (drawtext) ---
    for clip in graphic_clips:
        logo = next((e for e in clip.effects if e.type == EFFECT_LOGO_OVERLAY), None)
        cta = next((e for e in clip.effects if e.type == EFFECT_CTA_OVERLAY), None)
        start_s = _s(clip.start, fps)
        end_s = _s(clip.start + clip.out_point - clip.in_point, fps)
        if logo is not None:
            file = logo.params.get("file") or clip.source
            # -t acota el loop: un input infinito puede impedir que ffmpeg termine
            idx = add_input(("-loop", "1", "-framerate", str(fps), "-t", end_s,
                             "-i", path_of(file)))
            m = _num(float(logo.params.get("margin_rel", 0.04)))
            x_t, y_t = _CORNERS.get(logo.params.get("corner", "top_right"),
                                    _CORNERS["top_right"])
            chains.append(f"[{idx}:v]scale={cw}*{_num(LOGO_WIDTH_REL)}:-1[lg{step}]")
            out = f"[vlg{step}]"
            chains.append(
                f"{vlabel}[lg{step}]overlay=x={x_t.format(m=m)}:y={y_t.format(m=m)}"
                f":enable='between(t,{start_s},{end_s})'{out}")
            vlabel = out
            step += 1
        elif cta is not None:
            out = f"[vcta{step}]"
            chains.append(f"{vlabel}{_drawtext(cta.params, font_files, ch, start_s, end_s)}{out}")
            vlabel = out
            step += 1
        else:
            # slide de carrusel: imagen a pantalla completa en su ventana
            dur = _s(clip.out_point - clip.in_point, fps)
            idx = add_input(("-loop", "1", "-framerate", str(fps), "-t", dur,
                             "-i", path_of(clip.source)))
            chains.append(
                f"[{idx}:v]fps={fps},scale={cw}:{ch}:force_original_aspect_ratio=increase,"
                f"crop={cw}:{ch},setpts=PTS-STARTPTS+{start_s}/TB[sl{step}]")
            out = f"[vsl{step}]"
            chains.append(f"{vlabel}[sl{step}]overlay=x=0:y=0:eof_action=pass{out}")
            vlabel = out
            step += 1

    # --- subtítulos (ASS burn-in) ---
    ass_content = build_ass(ir)
    if ass_content is not None:
        fontsdir = _subtitle_fontsdir(ir, font_files)
        out = "[vsub]"
        ass = f"ass=filename='{ASS_PLACEHOLDER}'"
        if fontsdir:
            ass += f":fontsdir='{fontsdir}'"
        chains.append(f"{vlabel}{ass}{out}")
        vlabel = out

    # --- salida de vídeo por quality ---
    if quality == "preview":
        chains.append(f"{vlabel}scale=-2:{PREVIEW_HEIGHT}[vout]")
    else:
        spec = PLATFORM_MASTERS[platform]
        chains.append(f"{vlabel}scale={spec.width}:{spec.height},fps={spec.fps}[vout]")
    vlabel = "[vout]"

    # --- audio: voz (clips sin music_mix) + música (con music_mix) ---
    voice_labels = []
    music_chain_label = None
    k = 0
    for track in audio_tracks:
        for clip in track.clips:
            mix = next((e for e in clip.effects if e.type == EFFECT_MUSIC_MIX), None)
            idx = add_input(("-i", path_of(clip.source)))
            if mix is None:
                chains.append(
                    f"[{idx}:a]atrim=start={_s(clip.in_point, fps)}:end={_s(clip.out_point, fps)},"
                    f"asetpts=PTS-STARTPTS[va{k}]")
                voice_labels.append(f"[va{k}]")
                k += 1
            else:
                chains.append(_music_chain(clip, mix.params, idx, fps))
                music_chain_label = "[amusic]"
    alabel: str | None = None
    if voice_labels:
        if len(voice_labels) == 1:
            chains.append(f"{voice_labels[0]}anull[avoice]")
        else:
            chains.append(f"{''.join(voice_labels)}concat=n={len(voice_labels)}:v=0:a=1[avoice]")
        alabel = "[avoice]"
    if music_chain_label:
        if alabel:
            chains.append(f"{alabel}{music_chain_label}"
                          "amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]")
        else:
            chains.append(f"{music_chain_label}anull[aout]")
        alabel = "[aout]"

    output_args = _output_args(quality, platform, alabel)
    return RenderPlan(
        inputs=tuple(inputs),
        filter_complex=";".join(chains),
        video_label=vlabel,
        audio_label=alabel,
        output_args=output_args,
        ass_content=ass_content,
    )


def _check_effects(ir: TimelineIR) -> None:
    for track in ir.tracks:
        for clip in track.clips:
            for effect in clip.effects:
                if effect.type not in KNOWN_EFFECTS:
                    raise RenderPlanError(
                        f"effect fuera del catálogo: '{effect.type}' (clip {clip.id})")


def _video_clip_chain(clip, idx, k, fps, cw, ch, shift_start=False) -> str:
    """Chain de un clip de vídeo: trim → fps → cover al canvas → zoom opcional."""
    scale = clip.transform.scale
    if abs(scale - 1.0) > 1e-9:
        # ceil: 1080*1.7778 = 1919.99 truncaría a 1919 y el crop de 1920 no cabría
        cover = (f"scale=w=ceil(iw*{_num(scale)}):h=ceil(ih*{_num(scale)}),"
                 f"crop={cw}:{ch}")
    else:
        cover = f"scale={cw}:{ch}:force_original_aspect_ratio=increase,crop={cw}:{ch}"
    setpts = "PTS-STARTPTS"
    if shift_start:
        setpts += f"+{_s(clip.start, fps)}/TB"
    parts = [
        f"trim=start={_s(clip.in_point, fps)}:end={_s(clip.out_point, fps)}",
        f"setpts={setpts}", f"fps={fps}", cover,
    ]
    zoom = next((e for e in clip.effects if e.type == EFFECT_ZOOM), None)
    if zoom is not None:
        zf, zt = _num(zoom.params["scale_from"]), _num(zoom.params["scale_to"])
        n = clip.out_point - clip.in_point
        parts.append(
            f"zoompan=z='{zf}+({zt}-{zf})*on/{n}':d=1"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={cw}x{ch}:fps={fps}")
    label = f"[bv{k}]" if not shift_start else f"[bvo{k[1:]}]"
    return f"[{idx}:v]{','.join(parts)}{label}"


def _drawtext(params: dict, font_files: dict[str, str], canvas_h: int,
              start_s: str, end_s: str) -> str:
    text = params["text"].replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
    font = params.get("font", "")
    fontfile = ""
    if font:
        if font not in font_files:
            raise RenderPlanError(f"font de la ficha no disponible: '{font}'")
        fontfile = f":fontfile='{font_files[font]}'"
    color = params.get("color") or "#FFFFFF"
    size = round(canvas_h * CTA_FONT_SIZE_REL)
    return (f"drawtext=text='{text}'{fontfile}:fontcolor={color}:fontsize={size}"
            f":x=(w-text_w)/2:y=h*{_num(CTA_Y_REL)}"
            f":enable='between(t,{start_s},{end_s})'")


def _subtitle_fontsdir(ir: TimelineIR, font_files: dict[str, str]) -> str:
    style = next((e.params for t in ir.tracks if t.kind == "subtitle"
                  for c in t.clips for e in c.effects
                  if e.type == EFFECT_SUBTITLE_STYLE), {})
    font = style.get("font", "")
    if not font:
        return ""
    if font not in font_files:
        raise RenderPlanError(f"font de subtítulos de la ficha no disponible: '{font}'")
    path = font_files[font]
    return path.rsplit("/", 1)[0] if "/" in path else path


def _music_chain(clip, params: dict, idx: int, fps: int) -> str:
    """Música: atrim → volume determinista (duck_ranges con rampas) → loudnorm."""
    dur = _s(clip.out_point - clip.in_point, fps)
    volume_rel = float(params.get("volume_rel", 1.0))
    ranges = [(frames_to_s(r["start"], fps), frames_to_s(r["end"], fps))
              for r in params.get("duck_ranges", [])]
    expr = _duck_expr(ranges, volume_rel)
    lufs = _num(float(params.get("target_lufs", -14.0)))
    return (f"[{idx}:a]atrim=start=0:end={dur},asetpts=PTS-STARTPTS,"
            f"volume='{expr}':eval=frame,loudnorm=I={lufs}:TP=-1.5:LRA=11[amusic]")


def _duck_expr(ranges: list[tuple[float, float]], volume_rel: float) -> str:
    """Expresión de volumen fiel a los duck_ranges auditados de la IR (opción A).

    Rampas deterministas en los bordes (attack/release) para que el ducking
    suene suave sin recomputar nada escuchando la señal.
    """
    duck, drop = _num(DUCK_LEVEL_REL), _num(1.0 - DUCK_LEVEL_REL)
    expr = "1"
    for start, end in sorted(ranges, reverse=True):
        s, e = _num(start), _num(end)
        s_a, e_r = _num(start + DUCK_ATTACK_S), _num(end + DUCK_RELEASE_S)
        a, r = _num(DUCK_ATTACK_S), _num(DUCK_RELEASE_S)
        expr = (f"if(between(t,{s},{s_a}),1-{drop}*(t-{s})/{a},"
                f"if(between(t,{s_a},{e}),{duck},"
                f"if(between(t,{e},{e_r}),{duck}+{drop}*(t-{e})/{r},{expr})))")
    return f"{_num(volume_rel)}*({expr})"


def _output_args(quality: str, platform: str, alabel: str | None) -> tuple[str, ...]:
    args: list[str] = ["-map", "[vout]"]
    if alabel:
        args += ["-map", alabel]
    if quality == "preview":
        args += [*PREVIEW_VIDEO_ARGS]
        if alabel:
            args += [*PREVIEW_AUDIO_ARGS]
    else:
        spec = PLATFORM_MASTERS[platform]
        args += [*MASTER_VIDEO_ARGS, "-b:v", spec.video_bitrate, "-r", str(spec.fps)]
        if alabel:
            args += [*MASTER_AUDIO_ARGS, "-b:a", spec.audio_bitrate]
    if not alabel:
        args.append("-an")
    return tuple(args)
