"""Tests del contrato EditPlan (M6) — eval harness, no vibes."""
import pytest
from vios_contracts import (
    DurationRange,
    EditPlan,
    EditPlanValidationError,
    HookCandidate,
    HookSpec,
    MediaIntelligence,
    PlannedBeat,
    Playbook,
    SelectedMoment,
    validate_edit_plan,
)


def make_plan(**overrides) -> EditPlan:
    base = dict(
        project_id="p1",
        client_id="cliender",
        playbook_id="reel-educativo",
        platform="instagram",
        intent="educar sobre X",
        target_duration_s=30.0,
        structure=[
            PlannedBeat(name="hook", target_duration_s=3.0),
            PlannedBeat(name="desarrollo", target_duration_s=22.0),
            PlannedBeat(name="cta", target_duration_s=5.0),
        ],
        moments=[
            SelectedMoment(order=0, asset_id="a1", start_s=10.0, end_s=13.0,
                           beat="hook", why="frase con gancho"),
            SelectedMoment(order=1, asset_id="a1", start_s=20.0, end_s=42.0,
                           beat="desarrollo", why="explicación núcleo"),
            SelectedMoment(order=2, asset_id="a1", start_s=50.0, end_s=55.0,
                           beat="cta", why="cierre con llamada"),
        ],
        hooks=[HookCandidate(asset_id="a1", start_s=10.0, end_s=13.0,
                             text="¿Sabías que...?", score=0.9)],
    )
    base.update(overrides)
    return EditPlan(**base)


def make_playbook(**overrides) -> Playbook:
    base = dict(
        id="reel-educativo",
        name="Reel educativo",
        hook=HookSpec(max_seconds=3.5),
        ideal_duration={"instagram": DurationRange(min_s=15, max_s=60)},
    )
    base.update(overrides)
    return Playbook(**base)


def test_valid_plan_passes():
    validate_edit_plan(make_plan(), playbook=make_playbook())


def test_target_duration_out_of_playbook_range():
    plan = make_plan(
        target_duration_s=90.0,
        structure=[PlannedBeat(name="hook", target_duration_s=90.0)],
        moments=[], hooks=[],
    )
    with pytest.raises(EditPlanValidationError, match="ideal_duration"):
        validate_edit_plan(plan, playbook=make_playbook())


def test_beats_must_sum_target():
    plan = make_plan(structure=[PlannedBeat(name="hook", target_duration_s=5.0)])
    with pytest.raises(EditPlanValidationError, match="beats suman"):
        validate_edit_plan(plan)


def test_moment_orders_must_be_contiguous():
    plan = make_plan()
    bad = plan.model_copy(update={"moments": [
        plan.moments[0].model_copy(update={"order": 0}),
        plan.moments[1].model_copy(update={"order": 2}),
    ]})
    with pytest.raises(EditPlanValidationError, match="sin huecos"):
        validate_edit_plan(bad)


def test_moment_inverted_range():
    plan = make_plan()
    bad = plan.model_copy(update={"moments": [
        plan.moments[0].model_copy(update={"start_s": 13.0, "end_s": 10.0}),
    ]})
    with pytest.raises(EditPlanValidationError, match="end_s"):
        validate_edit_plan(bad)


def test_moment_why_required():
    plan = make_plan()
    bad = plan.model_copy(update={"moments": [
        plan.moments[0].model_copy(update={"why": "  "}),
    ]})
    with pytest.raises(EditPlanValidationError, match="why obligatorio"):
        validate_edit_plan(bad)


def test_moment_unknown_beat():
    plan = make_plan()
    bad = plan.model_copy(update={"moments": [
        plan.moments[0].model_copy(update={"beat": "inexistente"}),
    ]})
    with pytest.raises(EditPlanValidationError, match="no existe en structure"):
        validate_edit_plan(bad)


def test_moment_exceeds_asset_duration():
    mi = MediaIntelligence(asset_id="a1", source_hash="h", duration_s=40.0)
    with pytest.raises(EditPlanValidationError, match="excede"):
        validate_edit_plan(make_plan(), intelligence={"a1": mi})


def test_moment_asset_without_intelligence():
    with pytest.raises(EditPlanValidationError, match="sin intelligence"):
        validate_edit_plan(make_plan(), intelligence={})


def test_moments_sum_far_from_target():
    plan = make_plan(moments=[
        SelectedMoment(order=0, asset_id="a1", start_s=0.0, end_s=5.0,
                       beat="hook", why="x"),
    ])
    with pytest.raises(EditPlanValidationError, match="momentos suman"):
        validate_edit_plan(plan)


def test_hook_required_by_playbook():
    plan = make_plan(hooks=[])
    with pytest.raises(EditPlanValidationError, match="hook"):
        validate_edit_plan(plan, playbook=make_playbook())


def test_hook_too_long():
    plan = make_plan(hooks=[
        HookCandidate(asset_id="a1", start_s=0.0, end_s=10.0),
    ])
    with pytest.raises(EditPlanValidationError, match="máximo"):
        validate_edit_plan(plan, playbook=make_playbook())
