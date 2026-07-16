"""MediaIntelligence — análisis cacheado por asset (D4). STUB en M0 (detalle M4)."""
from pydantic import BaseModel, Field


class MediaIntelligence(BaseModel):
    schema_version: str = Field(default="0.0.1-stub")
    asset_id: str
    source_hash: str
    # M4: transcript word-level, escenas[], shots[], caras[], energia, silencios[], score_calidad
