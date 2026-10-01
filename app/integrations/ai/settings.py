from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    ai_provider: str = "gemini"
    ai_model: str = "gemini-3.5-flash-lite"
    gemini_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
