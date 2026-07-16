"""ClientProfile — identidad, biblioteca, reglas, objetivos. STUB en M0 (detalle M2)."""
from pydantic import BaseModel, Field


class ClientProfile(BaseModel):
    schema_version: str = Field(default="0.0.1-stub")
    client_id: str
    name: str
    # M2: branding, tipografias, colores, tono, biblioteca(embeddings), reglas, objetivos, cuentas
