from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Aegis Climate MVP"
    environment: str = "local"
    secret_key: str = "changeme"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    database_url: str = "postgresql+psycopg2://aegis:example@localhost:5432/aegis"
    redis_url: str = "redis://localhost:6379/0"

    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "aegis-data"

    code_version: str = "dev"

    model_config = SettingsConfigDict(env_prefix="AEGIS_", env_file=".env")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
