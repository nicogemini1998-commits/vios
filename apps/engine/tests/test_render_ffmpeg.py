"""M11 smoke real: render de la IR golden rev-7 con ffmpeg de verdad.

Skip si ffmpeg/ffprobe no están instalados (viven en el contenedor engine).
Los sources se sintetizan con lavfi — el smoke valida SINTAXIS y ejecución del
filtergraph, no estética (eso es la puerta humana con material real).
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from .test_render_m11 import asset_paths_for, load_ir


def _has_filters(*names: str) -> bool:
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        return False
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                         capture_output=True, text=True).stdout
    return all(f" {n} " in out for n in names)


pytestmark = pytest.mark.skipif(
    not _has_filters("ass", "drawtext", "zoompan", "loudnorm"),
    reason="ffmpeg completo no disponible (drawtext/ass requieren el build del "
           "contenedor engine; el de Homebrew viene sin freetype/libass)",
)

FONT_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]


def _synth(cmd: list[str]) -> None:
    subprocess.run(["ffmpeg", "-y", *cmd], check=True, capture_output=True)


def _probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        check=True, capture_output=True,
    )
    return json.loads(out.stdout)


@pytest.fixture(scope="module")
def sources(tmp_path_factory):
    d = tmp_path_factory.mktemp("sources")
    a1 = d / "a1.mp4"
    # 1920x1080 REAL: la IR trae el cover 1.7778 calculado para esas dims (M9)
    _synth(["-f", "lavfi", "-i", "testsrc=duration=60:size=1920x1080:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=60",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
            "-shortest", str(a1)])
    music = d / "music.mp3"
    _synth(["-f", "lavfi", "-i", "sine=frequency=220:duration=45", str(music)])
    logo = d / "logo.png"
    _synth(["-f", "lavfi", "-i", "color=c=white:s=200x80:d=1",
            "-frames:v", "1", str(logo)])
    return {"a1": str(a1), "music-1.mp3": str(music), "logo1b.png": str(logo)}


def _font_files():
    font = next((f for f in FONT_CANDIDATES if Path(f).exists()), None)
    if font is None:
        pytest.skip("sin font de sistema para el smoke de subtítulos")
    return {"Inter": font}


async def test_smoke_preview_rev7(sources, tmp_path):
    from vios_engine.render import (
        InMemoryRenderRepo,
        RenderQueue,
        RenderService,
        SubprocessFfmpegRunner,
    )

    ir = load_ir("reel_f4_rev7")
    paths = {**asset_paths_for(ir), **sources}
    svc = RenderService(InMemoryRenderRepo(), SubprocessFfmpegRunner(),
                        RenderQueue(1, 1), tmp_path, timeout_s=600.0)
    rec = await svc.render(ir, "preview", "instagram", "cliender",
                           paths, _font_files())
    assert rec.status == "done", rec.error
    info = _probe(Path(rec.url))
    codecs = {s["codec_type"] for s in info["streams"]}
    assert codecs == {"video", "audio"}
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert video["height"] == 480                       # preview 480p
    assert abs(float(info["format"]["duration"]) - 30.0) < 1.0


async def test_smoke_thumbnail(sources, tmp_path):
    from vios_engine.render import (
        InMemoryRenderRepo,
        RenderQueue,
        RenderService,
        SubprocessFfmpegRunner,
    )

    svc = RenderService(InMemoryRenderRepo(), SubprocessFfmpegRunner(),
                        RenderQueue(1, 1), tmp_path, timeout_s=60.0)
    out = await svc.thumbnail(sources["a1"], frame=345, fps=30,
                              out_path=tmp_path / "thumb.jpg")
    assert out.exists() and out.stat().st_size > 0
