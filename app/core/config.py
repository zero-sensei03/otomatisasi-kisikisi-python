from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "KisiKisi AI"
    app_env: str = "development"
    debug: bool = True

    secret_key: str

    database_url: str

    storage_path: str = "storage"
    max_upload_size: int = 10 * 1024 * 1024
    timezone: str = "Asia/Jakarta"

    session_cookie_name: str = "kisikisi_session"
    session_max_age: int = 8 * 60 * 60

    csrf_cookie_name: str = "kisikisi_csrf"
    csrf_max_age: int = 60 * 60

    admin_email: str = "devmeifa@gmail.com"
    admin_password: str = "MeiFaDev@123"
    admin_name: str = "MeiFa Administrator"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()