"""Application settings, loaded from environment variables (12-factor).

No infrastructure address is hard-coded here. Local development values live in
`.env` (see `.env.example`); production values come from the platform's secret
manager (e.g. AWS Secrets Manager / SSM) injected as environment variables.
"""
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"  # development | staging | production

    # --- persistence -------------------------------------------------------
    database_url: str
    db_pool_size: int = 10
    db_max_overflow: int = 10

    # --- auth --------------------------------------------------------------
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "sentinel-grc"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14
    min_password_length: int = 12
    google_client_id: str | None = None  # enables Google Sign-In when set

    # --- http --------------------------------------------------------------
    cors_origins: str = ""  # comma-separated explicit origins, never "*"

    # --- webhooks ---------------------------------------------------------
    webhook_allow_private: bool = False  # dev only: allow loopback/private targets

    # --- AI (used by later increments; kept so legacy code keeps working) ---
    llm_provider: str = "mock"
    hf_token: str | None = None
    hf_model: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def _normalize_database_url(self) -> "Settings":
        # Hosted Postgres (Neon, Supabase, Vercel Postgres) hands out postgres:// or
        # postgresql:// URLs; SQLAlchemy needs the psycopg (v3) driver spelled out.
        url = self.database_url
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                self.database_url = "postgresql+psycopg://" + url[len(prefix):]
                break
        return self

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        if "*" in self.cors_origin_list:
            raise ValueError("CORS_ORIGINS must list explicit origins, not '*'")
        if self.is_production:
            if self.jwt_secret.startswith("dev-"):
                raise ValueError("JWT_SECRET must be a real secret in production")
            if self.webhook_allow_private:
                raise ValueError("WEBHOOK_ALLOW_PRIVATE must be false in production")
            if any(o.startswith("http://") for o in self.cors_origin_list):
                raise ValueError("Production CORS origins must use https")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
