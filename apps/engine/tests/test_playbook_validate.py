"""M2 T5-T6: validación de playbooks."""
from pathlib import Path

import pytest
from vios_contracts import Playbook, PlaybookValidationError, validate_playbook
from vios_engine.playbooks import load_playbooks_dir

ROOT = Path(__file__).resolve().parents[3]


def test_t5_seed_playbooks_valid():
    pbs = load_playbooks_dir(ROOT / "playbooks")
    for pb in pbs.values():
        validate_playbook(pb)
        assert abs(sum(b.rel_duration for b in pb.beats) - 1.0) <= 0.01


def test_t6_beats_must_sum_to_one():
    pb = Playbook(
        id="bad", name="Bad",
        beats=[{"name": "a", "rel_duration": 0.3}, {"name": "b", "rel_duration": 0.3}],
    )
    with pytest.raises(PlaybookValidationError):
        validate_playbook(pb)


def test_t6_duration_min_gt_max_rejected():
    pb = Playbook(
        id="bad2", name="Bad2",
        beats=[{"name": "a", "rel_duration": 1.0}],
        ideal_duration={"instagram": {"min_s": 60, "max_s": 20}},
    )
    with pytest.raises(PlaybookValidationError):
        validate_playbook(pb)
