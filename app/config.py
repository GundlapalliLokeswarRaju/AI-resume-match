"""Application settings, loaded from environment / .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "ResuMatch AI"
    version: str = "1.0.0"

    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_timeout: float = 60.0
    groq_max_tokens: int = 4096
    groq_temperature: float = 0.2

    # Upload limits
    max_upload_bytes: int = 5 * 1024 * 1024  # 5 MB
    max_resume_chars: int = 30_000
    max_jd_chars: int = 20_000

    # Rate limiting — protects the shared Groq quota on the public demo.
    rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 600

    @property
    def llm_enabled(self) -> bool:
        return bool(self.groq_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
