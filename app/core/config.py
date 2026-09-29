from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Tesis Evaluasi"
    app_env: str = "development"
    debug: bool = True

    secret_key: str

    database_url: str

    session_cookie_name: str = "tesis_session"
    session_max_age: int = 28800

    storage_template_dir: str = "storage/templates"
    storage_generated_dir: str = "storage/generated"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
