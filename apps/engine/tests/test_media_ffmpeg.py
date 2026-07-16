"""M3 T8: impls reales ffprobe/ffmpeg. Skip si ffmpeg no está instalado."""
import shutil
import subprocess

import pytest
from vios_engine.media import FfmpegTranscoder, FfprobeProber

pytestmark = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="ffmpeg/ffprobe no instalados (viven en el contenedor engine)",
)


@pytest.fixture
def clip(tmp_path):
    out = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=30",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-c:v", "libx264", "-c:a", "aac", "-shortest", str(out)],
        capture_output=True, check=True,
    )
    return out


def test_probe_real(clip):
    meta = FfprobeProber().probe(clip)
    assert meta.width == 320 and meta.height == 240
    assert meta.duration_s == pytest.approx(1.0, abs=0.3)
    assert meta.has_audio is True


def test_proxy_real(clip, tmp_path):
    dst = tmp_path / "proxy.mp4"
    FfmpegTranscoder().make_proxy(clip, dst, height=120)
    assert dst.exists() and dst.stat().st_size > 0
