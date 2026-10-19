from functools import lru_cache
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "TalentOS"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"
    secret_key: str = "change-me-before-deployment"
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/talentos"
    db_pool_size: int = 10
    db_max_overflow: int = 10
    redis_url: str = "redis://localhost:6379/0"

    gemini_api_key: str | None = None
    gemini_api_key_2: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_model_2: str = "gemini-2.5-flash"
    xai_api_key: str | None = None
    grok_api_key: str | None = None  # Alias for deployments that name the xAI key GROK_API_KEY
    xai_model: str = "grok-3-mini"
    ai_request_timeout_seconds: float = 20.0
    ai_max_retries_per_provider: int = 1
    ai_provider_cooldown_seconds: int = 60

    admin_seed_email: str = "admin@talentos.com"
    admin_seed_password: str = "@talentos123"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value):
        if isinstance(value, str):
            if value.startswith("postgres://"):
                return value.replace("postgres://", "postgresql+asyncpg://", 1)
            if value.startswith("postgresql://"):
                return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.environment.lower() == "production":
            if self.debug:
                raise ValueError("DEBUG must be false in production")
            if self.secret_key == "change-me-before-deployment" or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must be a unique random value of at least 32 characters in production")
            if self.admin_seed_password == "@talentos123" or len(self.admin_seed_password) < 16:
                raise ValueError("Set a unique ADMIN_SEED_PASSWORD of at least 16 characters in production")
            if "*" in self.cors_origin_list:
                raise ValueError("Wildcard CORS origins are not allowed in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
