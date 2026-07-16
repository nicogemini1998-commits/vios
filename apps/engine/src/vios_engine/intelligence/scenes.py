"""PySceneDetectDetector (scenedetect). Import perezoso: instala extra [analysis]."""
from __future__ import annotations

from vios_contracts import Scene


class PySceneDetectDetector:
    def __init__(self, threshold: float = 27.0) -> None:
        self.threshold = threshold

    def detect(self, video_path: str) -> list[Scene]:  # pragma: no cover
        try:
            from scenedetect import ContentDetector, SceneManager, open_video
        except ImportError as exc:
            raise RuntimeError("scenedetect no instalado: `uv sync --extra analysis`") from exc

        video = open_video(video_path)
        sm = SceneManager()
        sm.add_detector(ContentDetector(threshold=self.threshold))
        sm.detect_scenes(video)
        scene_list = sm.get_scene_list()
        if not scene_list:  # plano unico -> 1 escena que cubre todo (CL4)
            dur = video.duration.get_seconds() if video.duration else 0.0
            return [Scene(index=0, start_s=0.0, end_s=dur)]
        return [
            Scene(index=i, start_s=start.get_seconds(), end_s=end.get_seconds())
            for i, (start, end) in enumerate(scene_list)
        ]
