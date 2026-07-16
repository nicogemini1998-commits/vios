"""WhisperTranscriber (faster-whisper). Import perezoso: instala extra [analysis]."""
from __future__ import annotations

from vios_contracts import Segment, Transcript, Word

# prob media por debajo -> low_confidence (base de [inaudible], manual §2.3)
_LOW_CONF = 0.5


class WhisperTranscriber:
    def __init__(
        self, model: str = "small", device: str = "cpu", compute_type: str = "int8"
    ) -> None:
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "faster-whisper no instalado: `uv sync --extra analysis`"
                ) from exc
            self._model = WhisperModel(
                self.model_name, device=self.device, compute_type=self.compute_type
            )
        return self._model

    def transcribe(  # pragma: no cover
        self, audio_path: str, language: str | None = None
    ) -> Transcript:
        model = self._load()
        segments, info = model.transcribe(
            audio_path, language=language, word_timestamps=True, beam_size=5,
        )
        out: list[Segment] = []
        for seg in segments:
            words = [
                Word(start_s=w.start, end_s=w.end, text=w.word, prob=w.probability or 1.0)
                for w in (seg.words or [])
            ]
            avg = sum(w.prob for w in words) / len(words) if words else 1.0
            out.append(Segment(
                start_s=seg.start, end_s=seg.end, text=seg.text.strip(),
                low_confidence=avg < _LOW_CONF, words=words,
            ))
        return Transcript(language=info.language or "", segments=out)
