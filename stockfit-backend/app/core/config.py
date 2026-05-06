from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "StockFit API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"

    # Database
    db_host: str
    db_port: int = 5432
    db_name: str = "postgres"
    db_user: str = "postgres"
    db_password: str

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
