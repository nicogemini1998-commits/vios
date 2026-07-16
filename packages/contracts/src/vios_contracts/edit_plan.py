"""EditPlan (M6) — salida del Director+Story Agent, entrada del Edit Agent.

Unidades en SEGUNDOS (dominio narrativo, relativo al source). El Edit Agent
convierte a frames con `fps` (frontera con Timeline IR).
Cada momento seleccionado anota POR QUÉ (auditable, eval-first: las reglas de
`validate_edit_plan` son el harness de evaluación, no vibes).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .media_intelligence import MediaIntelligence
from .playbook import Playbook

SCHEMA_VERSION = "1.0.0"

# tolerancias del eval harness
_BEAT_SUM_TOL = 0.15          # beats pueden desviarse ±15% del target
_MOMENT_SUM_TOL = 0.25        # suma de momentos ±25% del target


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class PlannedBeat(_Model):
    name: str
    purpose: str = ""
    target_duration_s: float


class SelectedMoment(_Model):
    order: int                   # posición en la edición (0-based, sin huecos)
    asset_id: str
    start_s: float
    end_s: float
    beat: str                    # nombre de PlannedBeat al que sirve
    why: str                     # justificación auditable, obligatoria


class HookCandidate(_Model):
    asset_id: str
    start_s: float
    end_s: float
    text: str = ""
    score: float = 0.0           # 0-1, confianza del agente
    why: str = ""


class EditPlan(_Model):
    schema_version: str = SCHEMA_VERSION
    project_id: str
    client_id: str
    playbook_id: str
    platform: str
    intent: str                  # qué debe lograr el vídeo
    arc: str = ""                # resumen del arco narrativo
    target_duration_s: float
    structure: list[PlannedBeat] = Field(default_factory=list)
    moments: list[SelectedMoment] = Field(default_factory=list)
    hooks: list[HookCandidate] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EditPlanValidationError(ValueError):
    """El EditPlan viola una regla semántica del eval harness."""


def validate_edit_plan(
    plan: EditPlan,
    playbook: Playbook | None = None,
    intelligence: dict[str, MediaIntelligence] | None = None,
) -> None:
    """Eval harness del EditPlan. Lanza EditPlanValidationError con causa exacta.

    - Duración objetivo > 0 y dentro de ideal_duration[platform] del playbook.
    - Beats planificados suman ~target_duration.
    - Momentos: rangos válidos, order 0..n-1 sin huecos, beat existente,
      dentro de la duración real del asset (si hay intelligence), suma ~target.
    - Hook: si el playbook lo exige, ≥1 candidato y ninguno supera max_seconds.
    """
    if plan.target_duration_s <= 0:
        raise EditPlanValidationError("target_duration_s debe ser > 0")

    if playbook is not None:
        rng = playbook.ideal_duration.get(plan.platform)
        if rng is not None and not (rng.min_s <= plan.target_duration_s <= rng.max_s):
            raise EditPlanValidationError(
                f"target_duration_s={plan.target_duration_s} fuera de "
                f"ideal_duration[{plan.platform}]=[{rng.min_s}, {rng.max_s}]"
            )

    if plan.structure:
        total = sum(b.target_duration_s for b in plan.structure)
        if abs(total - plan.target_duration_s) > plan.target_duration_s * _BEAT_SUM_TOL:
            raise EditPlanValidationError(
                f"beats suman {total:.1f}s, target {plan.target_duration_s:.1f}s "
                f"(tolerancia ±{_BEAT_SUM_TOL:.0%})"
            )
        for b in plan.structure:
            if b.target_duration_s <= 0:
                raise EditPlanValidationError(
                    f"beat '{b.name}': target_duration_s debe ser > 0"
                )

    beat_names = {b.name for b in plan.structure}
    orders = sorted(m.order for m in plan.moments)
    if orders != list(range(len(plan.moments))):
        raise EditPlanValidationError(
            f"orders de momentos deben ser 0..{len(plan.moments) - 1} sin huecos, son {orders}"
        )
    for m in plan.moments:
        if m.end_s <= m.start_s:
            raise EditPlanValidationError(
                f"momento order={m.order}: end_s ({m.end_s}) <= start_s ({m.start_s})"
            )
        if not m.why.strip():
            raise EditPlanValidationError(f"momento order={m.order}: why obligatorio")
        if beat_names and m.beat not in beat_names:
            raise EditPlanValidationError(
                f"momento order={m.order}: beat '{m.beat}' no existe en structure"
            )
        if intelligence is not None:
            mi = intelligence.get(m.asset_id)
            if mi is None:
                raise EditPlanValidationError(
                    f"momento order={m.order}: asset '{m.asset_id}' sin intelligence"
                )
            if mi.duration_s is not None and m.end_s > mi.duration_s + 0.01:
                raise EditPlanValidationError(
                    f"momento order={m.order}: end_s {m.end_s} excede "
                    f"duración del asset ({mi.duration_s}s)"
                )

    if plan.moments:
        total_m = sum(m.end_s - m.start_s for m in plan.moments)
        if abs(total_m - plan.target_duration_s) > plan.target_duration_s * _MOMENT_SUM_TOL:
            raise EditPlanValidationError(
                f"momentos suman {total_m:.1f}s, target {plan.target_duration_s:.1f}s "
                f"(tolerancia ±{_MOMENT_SUM_TOL:.0%})"
            )

    if playbook is not None and playbook.hook is not None:
        if plan.moments and not plan.hooks:
            raise EditPlanValidationError(
                "playbook exige hook y el plan no trae candidatos"
            )
        for h in plan.hooks:
            if h.end_s - h.start_s > playbook.hook.max_seconds + 0.01:
                raise EditPlanValidationError(
                    f"hook candidato dura {h.end_s - h.start_s:.1f}s, "
                    f"máximo {playbook.hook.max_seconds}s"
                )
