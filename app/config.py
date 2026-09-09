from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalizar_db_url(url: str) -> str:
    # Provedores (Render, Heroku) entregam postgres:// ou postgresql://.
    # O app usa o driver assíncrono asyncpg, que exige postgresql+asyncpg://.
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "GWI Materiais"
    environment: str = "production"
    database_url: str = "sqlite+aiosqlite:///./gwi_v2.db"

    @field_validator("database_url")
    @classmethod
    def _normalizar_db(cls, v: str) -> str:
        return normalizar_db_url(v)

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

    mfa_required_roles: list[str] = []


@lru_cache
def get_settings() -> Settings:
    return Settings()
