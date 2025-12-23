from functools import lru_cache
from typing import Optional

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
    geocoder_provider: str = "stub"
    parcel_provider: str = "stub"
    characteristics_provider: str = "stub"

    geocoder_http_base_url: Optional[str] = None
    geocoder_http_api_key: Optional[str] = None
    geocoder_http_api_key_header: str = "Authorization"
    geocoder_http_mapping_json: Optional[dict] = None

    parcel_http_base_url: Optional[str] = None
    parcel_http_api_key: Optional[str] = None
    parcel_http_api_key_header: str = "Authorization"
    parcel_http_mapping_json: Optional[dict] = None

    characteristics_http_base_url: Optional[str] = None
    characteristics_http_api_key: Optional[str] = None
    characteristics_http_api_key_header: str = "Authorization"
    characteristics_http_mapping_json: Optional[dict] = None

    provider_timeout_seconds: float = 7.0
    provider_connect_timeout_seconds: float = 3.0
    provider_max_retries: int = 2

    geocoder_url: str = ""
    parcel_url: str = ""
    characteristics_url: str = ""

    model_config = SettingsConfigDict(env_prefix="AEGIS_", env_file=".env")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
