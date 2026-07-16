"""Estado de job y fase (M5). Estructuras internas del motor.

`JobState` es el registro vivo de un job: estado global, estado por fase,
intentos y tokens gastados. El motor produce copias actualizadas (inmutable
hacia fuera: los consumidores reciben snapshots).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

JobStatus = Literal["pending", "running", "done", "failed"]
PhaseStatus = Literal["pending", "running", "done", "failed"]


class PhaseState(BaseModel):
    status: PhaseStatus = "pending"
    attempts: int = 0
    error: str = ""


class JobState(BaseModel):
    job_id: str
    project_id: str
    status: JobStatus = "pending"
    current_phase: str = ""
    phases: dict[str, PhaseState] = Field(default_factory=dict)
    tokens_spent: int = 0
    error: str = ""

    @classmethod
    def new(cls, job_id: str, project_id: str, phase_names: list[str]) -> JobState:
        return cls(
            job_id=job_id,
            project_id=project_id,
            phases={n: PhaseState() for n in phase_names},
        )
