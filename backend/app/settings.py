"""Runtime settings for security and operational controls."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SENTINEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_keys: str = ""
    allowed_origins: str = "http://localhost:8501,http://127.0.0.1:8501"
    rate_limit_per_minute: int = Field(default=120, ge=10, le=2000)
    max_body_bytes: int = Field(default=32_768, ge=1_024, le=5_000_000)
    expose_docs: bool = True
    enable_api_news_sources: bool = True
    enable_ai_advisor: bool = True

    newsapi_key: str = ""
    gnews_key: str = ""
    guardian_key: str = ""
    nyt_key: str = ""
    mediastack_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_seconds: int = Field(default=25, ge=5, le=120)

    live_query: str = "Strait of Hormuz OR GCC oil export OR LNG shipping disruption"

    @property
    def parsed_api_keys(self) -> set[str]:
        return {part.strip() for part in self.api_keys.split(",") if part.strip()}

    @property
    def parsed_allowed_origins(self) -> list[str]:
        if not self.allowed_origins.strip():
            return ["http://localhost:8501"]
        return [part.strip() for part in self.allowed_origins.split(",") if part.strip()]

    @property
    def api_news_keys_present(self) -> list[str]:
        present: list[str] = []
        if self.newsapi_key.strip():
            present.append("newsapi")
        if self.gnews_key.strip():
            present.append("gnews")
        if self.guardian_key.strip():
            present.append("guardian")
        if self.nyt_key.strip():
            present.append("nyt")
        if self.mediastack_key.strip():
            present.append("mediastack")
        return present


@lru_cache
def get_settings() -> Settings:
    return Settings()
