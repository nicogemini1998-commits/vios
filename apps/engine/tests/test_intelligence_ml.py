"""M4 T8: impls ML reales. Skip si faltan libs o ffmpeg."""
import importlib.util
import shutil
import subprocess

import pytest

_HAS = all(importlib.util.find_spec(m) for m in ("faster_whisper", "scenedetect")) \
    and shutil.which("ffmpeg") is not None

pytestmark = pytest.mark.skipif(
    not _HAS, reason="faster-whisper/scenedetect/ffmpeg no disponibles (contenedor)"
)


@pytest.fixture
def clip(tmp_path):
    out = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=30",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:v", "libx264", "-c:a", "aac", "-shortest", str(out)],
        capture_output=True, check=True,
    )
    return out


def test_scene_detect_real(clip):
    from vios_engine.intelligence.scenes import PySceneDetectDetector
    scenes = PySceneDetectDetector().detect(str(clip))
    assert len(scenes) >= 1
    assert scenes[0].end_s > scenes[0].start_s
