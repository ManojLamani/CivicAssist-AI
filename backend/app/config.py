from functools import lru_cache
from pathlib import Path

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore"
    )
    database_url: PostgresDsn


@lru_cache
def get_settings() -> Settings:
    return Settings()


class AuthSettings(BaseSettings):
    model_config = Settings.model_config
    jwt_secret: SecretStr = Field(min_length=32)


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()
