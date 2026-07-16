"""Config con fail-fast (RNF5): si falta una variable requerida, no arranca."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    supabase_url: str = "http://local"
    supabase_service_key: str = "local"
    storage_bucket: str = "vios-media"
    engine_port: int = 8000
    render_port: int = 4010
    llm_provider: str = "subscription"   # "subscription" (Claude Code, sin API) | "api"
    anthropic_api_key: str = ""          # solo si llm_provider="api"
    llm_model: str = "claude-sonnet-5"
    job_token_budget: int = 200_000      # presupuesto tokens por job (M5)


def load_settings() -> Settings:
    # Lanza ValidationError si falta DATABASE_URL u otra requerida.
    return Settings()
