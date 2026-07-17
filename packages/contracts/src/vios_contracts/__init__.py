"""VIOS shared contracts.

M1: Timeline IR (contrato central). M2: ClientProfile (ficha A-H) + Playbook.
MediaIntelligence sigue stub hasta M4.
"""
from .client_profile import CTA as ClientCTA
from .client_profile import (
    Asset,
    Audience,
    Blacklist,
    ClientProfile,
    ColorToken,
    Commercial,
    EditRules,
    FontRef,
    Identity,
    IntroOutro,
    Learning,
    Library,
    LogoRef,
    MusicRules,
    Pacing,
    Person,
    Target,
    VisualIdentity,
    Voice,
    client_missing_blocks,
    is_client_editable,
)
from .client_profile import SubtitleStyle as ClientSubtitleStyle
from .edit_plan import (
    EditPlan,
    EditPlanValidationError,
    HookCandidate,
    PlannedBeat,
    SelectedMoment,
    validate_edit_plan,
)
from .effects import (
    EFFECT_LOGO_OVERLAY,
    EFFECT_MUSIC_MIX,
    EFFECT_SUBTITLE_STYLE,
    EFFECT_ZOOM,
    KNOWN_EFFECTS,
)
from .media_intelligence import (
    EnergyPoint,
    Keyframe,
    MediaIntelligence,
    QualityScore,
    Scene,
    Segment,
    Silence,
    Transcript,
    Word,
)
from .playbook import (
    Beat,
    CTAPolicy,
    DurationRange,
    HookSpec,
    MusicPolicy,
    PacingPolicy,
    Playbook,
    PlaybookValidationError,
    SubtitlePolicy,
    validate_playbook,
)
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
    frames_to_s,
    from_json,
    s_to_frames,
    source_frame_to_timeline,
    timeline_end,
    to_json,
    validate,
)

__all__ = [
    # timeline
    "SCHEMA_VERSION", "Canvas", "Change", "Clip", "Decision", "Effect", "Marker",
    "Meta", "TimelineDraft", "TimelineIR", "TimelineValidationError", "Track",
    "Transform", "create_timeline", "diff", "export_json_schema", "frames_to_s",
    "from_json", "s_to_frames", "source_frame_to_timeline", "timeline_end",
    "to_json", "validate",
    # client profile (A-H)
    "Asset", "Audience", "Blacklist", "ClientCTA", "ClientProfile", "ClientSubtitleStyle",
    "ColorToken", "Commercial", "EditRules", "FontRef", "Identity", "Learning",
    "IntroOutro", "Library", "LogoRef", "MusicRules", "Pacing", "Person", "Target", "Voice",
    "VisualIdentity", "client_missing_blocks", "is_client_editable",
    # playbook
    "Beat", "CTAPolicy", "DurationRange", "HookSpec", "MusicPolicy", "PacingPolicy",
    "Playbook", "PlaybookValidationError", "SubtitlePolicy", "validate_playbook",
    # edit plan (M6)
    "EditPlan", "EditPlanValidationError", "HookCandidate", "PlannedBeat",
    "SelectedMoment", "validate_edit_plan",
    # effects (F4)
    "EFFECT_LOGO_OVERLAY", "EFFECT_MUSIC_MIX", "EFFECT_SUBTITLE_STYLE",
    "EFFECT_ZOOM", "KNOWN_EFFECTS",
    # media intelligence (M4)
    "MediaIntelligence", "Transcript", "Segment", "Word", "Scene", "Silence",
    "EnergyPoint", "Keyframe", "QualityScore",
]
