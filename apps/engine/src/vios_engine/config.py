"""Config con fail-fast (RNF5): si falta una variable requerida, no arranca."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    supabase_url: str = "http://local"
    supabase_service_key: str = "local"
    storage_bucket: str = "vios-media"
    engine_port: int = 8000
    llm_provider: str = "subscription"   # "subscription" (Claude Code, sin API) | "api"
    anthropic_api_key: str = ""          # solo si llm_provider="api"
    llm_model: str = "claude-sonnet-5"
    job_token_budget: int = 200_000      # presupuesto tokens por job (M5)
    render_max_concurrency: int = 2      # techo global de renders simultáneos (M11)
    render_max_per_client: int = 1       # techo por cliente — nadie monopoliza
    render_timeout_s: int = 600          # timeout de un render ffmpeg


def load_settings() -> Settings:
    # Lanza ValidationError si falta DATABASE_URL u otra requerida.
    return Settings()
