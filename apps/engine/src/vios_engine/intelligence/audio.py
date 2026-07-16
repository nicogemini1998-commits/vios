"""LibrosaAudioAnalyzer: energía RMS + silencios. Import perezoso: extra [analysis]."""
from __future__ import annotations

from vios_contracts import EnergyPoint, Silence


class LibrosaAudioAnalyzer:
    def __init__(self, top_db: float = 30.0, hop_length: int = 2048) -> None:
        self.top_db = top_db
        self.hop_length = hop_length

    def analyze(  # pragma: no cover
        self, audio_path: str
    ) -> tuple[list[EnergyPoint], list[Silence]]:
        try:
            import librosa
        except ImportError as exc:
            raise RuntimeError("librosa no instalado: `uv sync --extra analysis`") from exc

        y, sr = librosa.load(audio_path, sr=None, mono=True)
        rms = librosa.feature.rms(y=y, hop_length=self.hop_length)[0]
        times = librosa.frames_to_time(range(len(rms)), sr=sr, hop_length=self.hop_length)
        energy = [EnergyPoint(at_s=round(float(t), 3), rms=round(float(r), 5))
                  for t, r in zip(times, rms, strict=False)]

        # tramos NO silenciosos -> complemento = silencios
        intervals = librosa.effects.split(y, top_db=self.top_db, hop_length=self.hop_length)
        silences: list[Silence] = []
        prev_end = 0.0
        for start, end in intervals:
            s0, s1 = start / sr, end / sr
            if s0 - prev_end > 0.3:
                silences.append(Silence(start_s=round(prev_end, 3), end_s=round(s0, 3)))
            prev_end = s1
        total = len(y) / sr
        if total - prev_end > 0.3:
            silences.append(Silence(start_s=round(prev_end, 3), end_s=round(total, 3)))
        return energy, silences
