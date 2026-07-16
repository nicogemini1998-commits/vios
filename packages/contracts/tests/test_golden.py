"""T8: golden timelines contra 3 casos reales. Regenera con VIOS_UPDATE_GOLDEN=1."""
import os
from pathlib import Path

import pytest
from builders import build_carousel_video, build_podcast_clip, build_reel
from vios_contracts import from_json, to_json

GOLDEN = Path(__file__).resolve().parent / "golden"

CASES = {
    "reel_educativo": build_reel,
    "podcast_clip": build_podcast_clip,
    "carousel_video": build_carousel_video,
}


@pytest.mark.parametrize("name,builder", CASES.items())
def test_t8_golden(name, builder):
    ir = builder()
    path = GOLDEN / f"{name}.json"
    rendered = to_json(ir)
    if os.environ.get("VIOS_UPDATE_GOLDEN") == "1" or not path.exists():
        path.write_text(rendered + "\n", encoding="utf-8")
    expected = path.read_text().rstrip("\n")
    assert rendered == expected
    # y el golden re-parsea a una IR equivalente
    assert from_json(expected) == ir
