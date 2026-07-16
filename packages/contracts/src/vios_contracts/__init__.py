"""VIOS shared contracts.

M1: Timeline IR completa (contrato central). ClientProfile/Playbook/MediaIntelligence
siguen como stubs hasta M2/M4.
"""
from .client_profile import ClientProfile
from .media_intelligence import MediaIntelligence
from .playbook import Playbook
from .timeline_draft import TimelineDraft
from .timeline_ir import (
    SCHEMA_VERSION,
    Canvas,
    Clip,
    Decision,
    Effect,
    Marker,
    Meta,
    TimelineIR,
    Track,
    Transform,
    create_timeline,
)
from .timeline_ops import (
    Change,
    TimelineValidationError,
    diff,
    export_json_schema,
    from_json,
    to_json,
    validate,
)

__all__ = [
    "SCHEMA_VERSION",
    "Canvas",
    "Change",
    "Clip",
    "ClientProfile",
    "Decision",
    "Effect",
    "Marker",
    "MediaIntelligence",
    "Meta",
    "Playbook",
    "TimelineDraft",
    "TimelineIR",
    "TimelineValidationError",
    "Track",
    "Transform",
    "create_timeline",
    "diff",
    "export_json_schema",
    "from_json",
    "to_json",
    "validate",
]
