from vios_contracts import Canvas, TimelineDraft, create_timeline


def base_ir():
    return create_timeline(
        project_id="proj-1",
        fps=30,
        canvas=Canvas(width=1080, height=1920, aspect="9:16"),
        platform="instagram",
        playbook="reel-educativo",
    )


def build_reel():
    """Reel educativo: 1 video track (2 cortes) + subtitle + hook marker."""
    d = TimelineDraft.from_ir(base_ir())
    vt = d.add_track("video")
    d.add_clip(vt, source="asset-a", start=0, in_point=0, out_point=90)
    d.add_clip(vt, source="asset-a", start=90, in_point=300, out_point=450)
    st = d.add_track("subtitle")
    d.add_clip(st, source="Hola, esto es un reel", start=0, in_point=0, out_point=90)
    d.add_marker("hook", at=0, label="Hook 0-1.5s")
    return d.commit(by="edit-agent", why="Reel v1: 2 cortes + subs + hook")


def build_podcast_clip():
    """Podcast->clip: video track (1 corte largo) + beat markers."""
    d = TimelineDraft.from_ir(base_ir())
    vt = d.add_track("video")
    d.add_clip(vt, source="pod-1", start=0, in_point=1200, out_point=2100)
    d.add_marker("beat", at=0, label="entrada")
    d.add_marker("beat", at=450, label="punchline")
    d.add_marker("cta", at=840, label="sigue el canal")
    return d.commit(by="story-agent", why="Clip de podcast: mejor momento + beats")


def build_carousel_video():
    """Carrusel-video: 3 clips graphic + audio de fondo."""
    d = TimelineDraft.from_ir(base_ir())
    gt = d.add_track("graphic")
    for i in range(3):
        d.add_clip(gt, source=f"slide-{i}", start=i * 60, in_point=0, out_point=60)
    at = d.add_track("audio")
    d.add_clip(at, source="music-1", start=0, in_point=0, out_point=180)
    return d.commit(by="visual-agent", why="Carrusel-video: 3 slides + musica")
