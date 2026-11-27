"""Application settings, read from environment variables (or a local .env file).

pydantic-settings validates types for us: if DATABASE_URL is missing, the app
refuses to start with a clear error instead of failing later in a request.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    auth_mode: Literal["local", "supabase"] = "local"
    database_url: str
    local_jwt_secret: str | None = None
    local_jwt_ttl_minutes: int = 60 * 8
    supabase_url: str | None = None
    supabase_jwt_secret: str | None = None
    cors_origins: str = "http://localhost:3000"
    environment: Literal["development", "test", "staging", "production"] = "development"
    api_prefix: str = "/api/v1"
    min_password_length: int = Field(default=10, ge=8)

    @model_validator(mode="after")
    def _check_auth_secrets(self) -> "Settings":
        if self.auth_mode == "local":
            if not self.local_jwt_secret or len(self.local_jwt_secret) < 32:
                raise ValueError("LOCAL_JWT_SECRET must be set to at least 32 characters when AUTH_MODE=local")
            if self.environment == "production":
                raise ValueError("AUTH_MODE=local is for development only; use AUTH_MODE=supabase in production")
        if self.auth_mode == "supabase" and not self.supabase_jwt_secret:
            raise ValueError("SUPABASE_JWT_SECRET is required when AUTH_MODE=supabase")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
