from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
    judge0_api_url: str | None = None
    judge0_api_key: str | None = None
    judge0_poll_interval_seconds: float = 1.5
    judge0_timeout_seconds: int = 45

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
        if not isinstance(value, str):
            return value

        if value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql+asyncpg://", 1)
        elif value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+asyncpg://", 1)

        # Neon commonly supplies sslmode=require, which is a libpq option.
        # asyncpg expects the equivalent URL option to be named ssl.
        if value.startswith("postgresql+asyncpg://"):
            parts = urlsplit(value)
            query = [
                (key, "require" if key == "sslmode" and val == "require" else val)
                for key, val in parse_qsl(parts.query, keep_blank_values=True)
                if key != "sslmode"
            ]
            original_query = parse_qsl(parts.query, keep_blank_values=True)
            if any(key == "sslmode" for key, _ in original_query):
                sslmode = next(val for key, val in original_query if key == "sslmode")
                if not any(key == "ssl" for key, _ in query):
                    query.append(("ssl", "require" if sslmode == "require" else sslmode))
            value = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
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
