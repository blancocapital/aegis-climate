from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Aegis Climate MVP"
    environment: str = "local"
    secret_key: str = "changeme"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    class Config:
        env_prefix = "AEGIS_"


def get_settings() -> Settings:
    return Settings()
