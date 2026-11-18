"""Reranker settings — env-driven, never hardcoded at call sites."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class RerankerSettings(BaseSettings):
    reranker_model_name: str = "BAAI/bge-reranker-v2-m3"
    reranker_device: str = "cpu"
    reranker_max_retries: int = 2

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = RerankerSettings()
