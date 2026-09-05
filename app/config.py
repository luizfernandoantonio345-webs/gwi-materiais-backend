from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "GWI Materiais"
    environment: str = "production"
    database_url: str = "sqlite+aiosqlite:///./gwi_v2.db"

    secret_key: str = "CHANGE-ME-256-bit-secret-in-production-via-env"
    algorithm: str = "HS256"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 7

    default_tenant: str = "GRAMO"
    qr_base_url: str = "https://gwi.gramo.com/m"

    max_login_attempts: int = 5
    lockout_minutes: int = 15
    rate_limit_per_min: int = 120
    rate_limit_login_per_min: int = 10

    alcada_padrao_gerente: float = 50000.0

    cors_origins: list[str] = ["https://gwi.gramo.com"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
