"""M4 T1-T7: orquestación análisis con fakes, cache, sampler, score, round-trip."""

from vios_contracts import (
    EnergyPoint,
    MediaIntelligence,
    Scene,
    Segment,
    Silence,
    Transcript,
    Word,
)
from vios_engine.intelligence import (
    InMemoryIntelligenceCache,
    MidpointFrameSampler,
    analyze_asset,
    score_quality,
)
from vios_engine.media.models import AssetRecord, MediaMeta


def _asset(has_audio=True, height=1920, duration=10.0):
    return AssetRecord(
        id="a1", project_id="p1", hash="h1",
        original_url="file:///orig.mp4", proxy_url="file:///proxy.mp4",
        audio_url="file:///audio.wav" if has_audio else None,
        meta=MediaMeta(duration_s=duration, width=1080, height=height,
                       fps=30.0, has_audio=has_audio),
    )


class FakeTranscriber:
    def __init__(self): self.calls = 0
    def transcribe(self, audio_path, language=None):
        self.calls += 1
        return Transcript(language="es", segments=[
            Segment(start_s=0, end_s=2, text="Hola mundo",
                    words=[Word(start_s=0, end_s=1, text="Hola", prob=0.9),
                           Word(start_s=1, end_s=2, text="mundo", prob=0.9)]),
        ])


class FakeSceneDetector:
    def __init__(self): self.calls = 0
    def detect(self, video_path):
        self.calls += 1
        return [Scene(index=0, start_s=0, end_s=5), Scene(index=1, start_s=5, end_s=10)]


class FakeAudioAnalyzer:
    def __init__(self): self.calls = 0
    def analyze(self, audio_path):
        self.calls += 1
        return ([EnergyPoint(at_s=0.0, rms=0.1)], [Silence(start_s=4, end_s=5)])


def _deps():
    return dict(
        transcriber=FakeTranscriber(),
        scene_detector=FakeSceneDetector(),
        audio_analyzer=FakeAudioAnalyzer(),
        frame_sampler=MidpointFrameSampler(),
        cache=InMemoryIntelligenceCache(),
    )


def test_t1_analyze_populated():
    mi = analyze_asset(_asset(), **_deps())
    assert mi.transcript.segments and mi.scenes and mi.silences
    assert mi.energy and mi.keyframes
    assert mi.duration_s == 10.0 and mi.fps == 30.0
    assert (mi.width, mi.height) == (1080, 1920)   # dims del ffprobe → base reframe M9
    assert mi.quality.audio_ok is True


def test_t2_cache_hit_no_recompute():
    deps = _deps()
    analyze_asset(_asset(), **deps)
    analyze_asset(_asset(), **deps)
    assert deps["transcriber"].calls == 1
    assert deps["scene_detector"].calls == 1


def test_t3_no_audio_skips_transcript():
    deps = _deps()
    mi = analyze_asset(_asset(has_audio=False), **deps)
    assert mi.transcript.segments == []
    assert mi.quality.audio_ok is False
    assert deps["transcriber"].calls == 0
    assert deps["audio_analyzer"].calls == 0
    assert mi.scenes  # las escenas sí se detectan


def test_t4_midpoint_sampler():
    scenes = [Scene(index=0, start_s=0, end_s=4), Scene(index=1, start_s=4, end_s=10)]
    frames = MidpointFrameSampler().sample(scenes, 10.0)
    assert [f.at_s for f in frames] == [2.0, 7.0]
    assert [f.scene_index for f in frames] == [0, 1]


def test_t5_score_heuristics():
    q = score_quality(_asset(has_audio=False), Transcript(), [])
    assert q.audio_ok is False
    assert any("audio" in n.lower() for n in q.notes)
    many = [Silence(start_s=i, end_s=i + 0.5) for i in range(8)]
    q2 = score_quality(
        _asset(height=480),
        Transcript(segments=[Segment(start_s=0, end_s=1, text="x")]),
        many,
    )
    assert any("baja" in n.lower() for n in q2.notes)
    assert any("silencio" in n.lower() for n in q2.notes)


def test_t6_low_confidence_marking():
    seg = Segment(start_s=0, end_s=1, text="algo",
                  words=[Word(start_s=0, end_s=1, text="algo", prob=0.3)])
    # el marcado lo hace el transcriber real; aquí verificamos que el campo existe y se preserva
    assert seg.low_confidence is False
    seg2 = Segment(start_s=0, end_s=1, text="[dudoso]", low_confidence=True)
    assert seg2.low_confidence is True and seg2.text == "[dudoso]"


def test_t7_media_intelligence_round_trip():
    mi = analyze_asset(_asset(), **_deps())
    restored = MediaIntelligence.model_validate_json(mi.model_dump_json())
    assert restored == mi
