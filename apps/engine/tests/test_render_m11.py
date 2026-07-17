"""Tests M11: ir_to_filtergraph puro (goldens), ASS, cola con rate limits, service.

Ningún test ejecuta ffmpeg real (FakeFfmpegRunner); el smoke real vive en
test_render_ffmpeg.py (skip sin ffmpeg, corre en contenedor/local).
"""
import asyncio
import json
from pathlib import Path

import pytest
from vios_contracts import (
    Canvas,
    TimelineDraft,
    create_timeline,
    from_json,
)
from vios_engine.render import (
    FakeFfmpegRunner,
    InMemoryRenderRepo,
    RenderPlanError,
    RenderQueue,
    RenderService,
    build_ass,
    ir_to_filtergraph,
    render_key,
)

CONTRACTS_GOLDEN = (Path(__file__).resolve().parents[3]
                    / "packages" / "contracts" / "tests" / "golden")
FILTERGRAPH_GOLDEN = Path(__file__).parent / "golden"

GOLDEN_IRS = ["reel_educativo", "podcast_clip", "carousel_video", "reel_f4_rev7"]

FONTS = {"Inter": "/fonts/Inter.ttf"}


def load_ir(name: str):
    return from_json((CONTRACTS_GOLDEN / f"{name}.json").read_text(encoding="utf-8"))


def asset_paths_for(ir) -> dict[str, str]:
    """Paths fake para todo source que el plan busca en storage."""
    paths: dict[str, str] = {}
    for track in ir.tracks:
        for clip in track.clips:
            if track.kind in ("video", "audio"):
                paths[clip.source] = f"/assets/{clip.source}"
            elif track.kind == "graphic":
                if any(e.type == "cta_overlay" for e in clip.effects):
                    continue
                logo = next((e for e in clip.effects if e.type == "logo_overlay"), None)
                src = (logo.params.get("file") or clip.source) if logo else clip.source
                paths[src] = f"/assets/{src}"
    return paths


# --- ir_to_filtergraph: goldens (el corazón, ANTES de ffmpeg real) ---

@pytest.mark.parametrize("name", GOLDEN_IRS)
def test_filtergraph_golden(name):
    ir = load_ir(name)
    plan = ir_to_filtergraph(ir, asset_paths_for(ir), "preview", "instagram",
                             font_files=FONTS)
    expected = json.loads(
        (FILTERGRAPH_GOLDEN / f"filtergraph_{name}.json").read_text(encoding="utf-8"))
    assert plan.filter_complex == expected["filter_complex"]
    assert [list(t) for t in plan.inputs] == expected["inputs"]
    assert list(plan.output_args) == expected["output_args"]
    assert (plan.ass_content is not None) == expected["has_ass"]


def test_filtergraph_master_usa_platform_masters():
    ir = load_ir("reel_f4_rev7")
    plan = ir_to_filtergraph(ir, asset_paths_for(ir), "master", "instagram",
                             font_files=FONTS)
    assert "scale=1080:1920,fps=30[vout]" in plan.filter_complex
    assert "-b:v" in plan.output_args and "10M" in plan.output_args
    assert "-profile:v" in plan.output_args


def test_filtergraph_effect_desconocido_error():
    base = create_timeline("p1", 30, Canvas(width=1080, height=1920, aspect="9:16"),
                           "instagram", "reel")
    d = TimelineDraft.from_ir(base)
    vt = d.add_track("video")
    d.add_clip(vt, source="a1", start=0, in_point=0, out_point=90,
               effects=[{"type": "explosion_3d", "params": {}}])
    ir = d.commit(by="t", why="effect inventado")
    with pytest.raises(RenderPlanError, match="explosion_3d"):
        ir_to_filtergraph(ir, {"a1": "/assets/a1"}, "preview", "instagram")


def test_filtergraph_asset_sin_path_error():
    ir = load_ir("podcast_clip")
    with pytest.raises(RenderPlanError, match="pod-1"):
        ir_to_filtergraph(ir, {}, "preview", "instagram")


def test_filtergraph_font_ausente_error():
    ir = load_ir("reel_f4_rev7")          # subtítulos con font Inter de la ficha
    with pytest.raises(RenderPlanError, match="Inter"):
        ir_to_filtergraph(ir, asset_paths_for(ir), "preview", "instagram",
                          font_files={})


def test_filtergraph_timeline_vacia_error():
    base = create_timeline("p1", 30, Canvas(width=1080, height=1920, aspect="9:16"),
                           "instagram", "reel")
    with pytest.raises(RenderPlanError, match="vacía"):
        ir_to_filtergraph(base, {}, "preview", "instagram")


def test_filtergraph_broll_overlay_con_pts_desplazado():
    """Track de vídeo overlay (b-roll M10) → setpts desplazado + overlay pass."""
    base = create_timeline("p1", 30, Canvas(width=1080, height=1920, aspect="9:16"),
                           "instagram", "reel")
    d = TimelineDraft.from_ir(base)
    vt = d.add_track("video")
    d.add_clip(vt, source="a1", start=0, in_point=0, out_point=300)
    bt = d.add_track("video")
    d.add_clip(bt, source="broll-1.mp4", start=120, in_point=0, out_point=60)
    ir = d.commit(by="t", why="base + b-roll")
    plan = ir_to_filtergraph(ir, {"a1": "/a", "broll-1.mp4": "/b"},
                             "preview", "instagram")
    assert "setpts=PTS-STARTPTS+4.000000/TB" in plan.filter_complex
    assert "overlay=x=0:y=0:eof_action=pass" in plan.filter_complex


def test_ducking_expr_con_rampas():
    """Opción A de Nico: volume con between + rampas attack/release deterministas."""
    ir = load_ir("reel_f4_rev7")
    plan = ir_to_filtergraph(ir, asset_paths_for(ir), "preview", "instagram",
                             font_files=FONTS)
    # duck_range 0-90f = 0-3s → attack 0-0.15, hold a 0.3, release 3.0-3.3
    assert "volume='0.700000*(" in plan.filter_complex
    assert "if(between(t,0.000000,0.150000),1-0.700000*(t-0.000000)/0.150000" \
        in plan.filter_complex
    assert "loudnorm=I=-14.000000" in plan.filter_complex


# --- ASS ---

def test_ass_lineas_con_estilo_de_ficha():
    ass = build_ass(load_ir("reel_f4_rev7"))
    assert "Style: Default,Inter," in ass
    assert "&H00FFFFFF" in ass                       # #FFFFFF exacto de la ficha
    assert "Dialogue: 0,0:00:00.00,0:00:03.00,Default,,0,0,0,,¿Sabías que el 80% falla?" in ass
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass


def test_ass_karaoke_por_palabra():
    base = create_timeline("p1", 30, Canvas(width=1080, height=1920, aspect="9:16"),
                           "instagram", "reel")
    d = TimelineDraft.from_ir(base)
    st = d.add_track("subtitle")
    style = {"type": "subtitle_style", "params": {"font": "Inter", "karaoke": True,
                                                  "color_base": "#C6FF00"}}
    d.add_clip(st, source="hola", start=0, in_point=0, out_point=15, effects=[style])
    d.add_clip(st, source="mundo", start=15, in_point=0, out_point=30, effects=[style])
    ass = build_ass(d.commit(by="t", why="karaoke"))
    assert "{\\k50}hola" in ass                      # 15f a 30fps = 0.5s = 50cs
    assert "{\\k100}mundo" in ass
    assert "&H0000FFC6" in ass                       # #C6FF00 → BGR


def test_ass_sin_subtitulos_none():
    assert build_ass(load_ir("podcast_clip")) is None


# --- cola: rate limits (directiva) ---

async def test_queue_respeta_techo_global():
    q = RenderQueue(max_concurrency=2, max_per_client=5)
    active, peak = [0], [0]

    async def job():
        async with q.slot("c1"):
            active[0] += 1
            peak[0] = max(peak[0], active[0])
            await asyncio.sleep(0.01)
            active[0] -= 1

    await asyncio.gather(*(job() for _ in range(6)))
    assert peak[0] <= 2


async def test_queue_limite_por_cliente():
    q = RenderQueue(max_concurrency=4, max_per_client=1)
    active, peak = {"c1": 0}, {"c1": 0}

    async def job():
        async with q.slot("c1"):
            active["c1"] += 1
            peak["c1"] = max(peak["c1"], active["c1"])
            await asyncio.sleep(0.01)
            active["c1"] -= 1

    await asyncio.gather(*(job() for _ in range(4)))
    assert peak["c1"] == 1                           # un cliente no monopoliza


# --- service ---

def make_service(tmp_path, runner=None):
    return RenderService(InMemoryRenderRepo(), runner or FakeFfmpegRunner(),
                         RenderQueue(2, 1), tmp_path, timeout_s=5.0)


async def test_service_render_feliz(tmp_path):
    ir = load_ir("reel_f4_rev7")
    svc = make_service(tmp_path)
    rec = await svc.render(ir, "preview", "instagram", "cliender",
                           asset_paths_for(ir), FONTS)
    assert rec.status == "done"
    assert rec.url.endswith(".mp4")
    assert rec.id == render_key("p1", 7, "preview", "instagram")
    assert (tmp_path / f"{rec.id}.ass").exists()     # ASS materializado


async def test_service_idempotente_devuelve_cache(tmp_path):
    ir = load_ir("reel_f4_rev7")
    runner = FakeFfmpegRunner()
    svc = make_service(tmp_path, runner)
    first = await svc.render(ir, "preview", "instagram", "cliender",
                             asset_paths_for(ir), FONTS)
    second = await svc.render(ir, "preview", "instagram", "cliender",
                              asset_paths_for(ir), FONTS)
    assert second.url == first.url
    assert len(runner.calls) == 1                    # NO re-renderiza


async def test_service_ffmpeg_error_reportado(tmp_path):
    ir = load_ir("reel_f4_rev7")
    svc = make_service(tmp_path, FakeFfmpegRunner(fail_with="exit 1: filtro roto"))
    rec = await svc.render(ir, "preview", "instagram", "cliender",
                           asset_paths_for(ir), FONTS)
    assert rec.status == "error"
    assert "filtro roto" in rec.error


async def test_service_plan_error_reportado(tmp_path):
    ir = load_ir("reel_f4_rev7")
    rec = await make_service(tmp_path).render(ir, "preview", "instagram",
                                              "cliender", {}, FONTS)
    assert rec.status == "error"
    assert "asset sin path" in rec.error


async def test_service_thumbnail_args(tmp_path):
    runner = FakeFfmpegRunner()
    svc = make_service(tmp_path, runner)
    out = await svc.thumbnail("/assets/a1", frame=345, fps=30,
                              out_path=tmp_path / "thumb.jpg")
    assert out.name == "thumb.jpg"
    args = runner.calls[0]
    assert args[:2] == ["-ss", "11.500000"]
    assert "-frames:v" in args
