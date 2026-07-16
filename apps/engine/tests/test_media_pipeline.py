"""M3 T1-T7: pipeline de ingesta con fakes (sin ffmpeg ni Supabase)."""
from pathlib import Path

import pytest
from vios_engine.media import (
    InMemoryAssetRepo,
    LocalStorage,
    MediaMeta,
    ingest_media,
    sha256_file,
)
from vios_engine.media.probe import ProbeError


class FakeProber:
    def __init__(self, meta=None, raises=False):
        self.meta = meta or MediaMeta(
            duration_s=10.0, width=1080, height=1920, fps=30.0, has_audio=True
        )
        self.raises = raises

    def probe(self, path):
        if self.raises:
            raise ProbeError("archivo corrupto")
        return self.meta


class FakeTranscoder:
    def __init__(self):
        self.proxy_calls = 0
        self.audio_calls = 0

    def make_proxy(self, src, dst, height=480):
        self.proxy_calls += 1
        Path(dst).write_bytes(b"proxy")

    def extract_audio(self, src, dst):
        self.audio_calls += 1
        Path(dst).write_bytes(b"audio")


@pytest.fixture
def src(tmp_path):
    f = tmp_path / "bruto.mp4"
    f.write_bytes(b"contenido de video de prueba")
    return f


def _deps(tmp_path):
    return dict(
        storage=LocalStorage(tmp_path / "store"),
        prober=FakeProber(),
        transcoder=FakeTranscoder(),
        repo=InMemoryAssetRepo(),
    )


def test_t1_ingest_ready(src, tmp_path):
    deps = _deps(tmp_path)
    res = ingest_media("proj-1", src, **deps)
    r = res.record
    assert res.cached is False
    assert r.status == "ready"
    assert r.original_url and r.proxy_url and r.audio_url
    assert r.meta.width == 1080


def test_t2_hash_cache_dedup(src, tmp_path):
    deps = _deps(tmp_path)
    r1 = ingest_media("proj-1", src, **deps)
    r2 = ingest_media("proj-1", src, **deps)
    assert r1.cached is False and r2.cached is True
    assert r1.record.id == r2.record.id
    assert deps["transcoder"].proxy_calls == 1  # no re-transcodifica


def test_t3_no_audio_skips_extraction(src, tmp_path):
    tc = FakeTranscoder()
    res = ingest_media(
        "proj-1", src,
        storage=LocalStorage(tmp_path / "s"),
        prober=FakeProber(meta=MediaMeta(duration_s=5, width=720, height=1280, has_audio=False)),
        transcoder=tc,
        repo=InMemoryAssetRepo(),
    )
    assert res.record.audio_url is None
    assert tc.audio_calls == 0


def test_t4_probe_error_marks_error(src, tmp_path):
    res = ingest_media(
        "proj-1", src,
        storage=LocalStorage(tmp_path / "s"),
        prober=FakeProber(raises=True),
        transcoder=FakeTranscoder(),
        repo=InMemoryAssetRepo(),
    )
    assert res.record.status == "error"
    assert "corrupto" in res.record.error
    assert res.record.meta.width is None  # sin metadata inventada


def test_t5_sha256_stable(tmp_path):
    a = tmp_path / "a"
    a.write_bytes(b"hola")
    b = tmp_path / "b"
    b.write_bytes(b"hola")
    c = tmp_path / "c"
    c.write_bytes(b"adios")
    assert sha256_file(a) == sha256_file(b)
    assert sha256_file(a) != sha256_file(c)


def test_t6_local_storage(tmp_path):
    st = LocalStorage(tmp_path / "store")
    f = tmp_path / "x.txt"
    f.write_text("y")
    url = st.put(f, "k/x.txt")
    assert st.exists("k/x.txt")
    assert url.startswith("file://")
    assert not st.exists("nope")


def test_t7_repo_find_by_hash(src, tmp_path):
    deps = _deps(tmp_path)
    res = ingest_media("proj-1", src, **deps)
    assert deps["repo"].find_by_hash(res.record.hash) is not None
    assert deps["repo"].find_by_hash("x" * 64) is None


def test_t4b_transcode_error_marks_error(src, tmp_path):
    from vios_engine.media.transcode import TranscodeError

    class BoomTranscoder:
        def make_proxy(self, src, dst, height=480):
            raise TranscodeError("ffmpeg peto")

        def extract_audio(self, src, dst):
            pass

    res = ingest_media(
        "proj-1", src,
        storage=LocalStorage(tmp_path / "s"),
        prober=FakeProber(),
        transcoder=BoomTranscoder(),
        repo=InMemoryAssetRepo(),
    )
    assert res.record.status == "error"
    assert "peto" in res.record.error
    assert res.record.meta.width == 1080  # metadata real conservada, solo falla el proxy
