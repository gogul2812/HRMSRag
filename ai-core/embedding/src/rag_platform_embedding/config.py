"""Embedding settings — never hardcode tenant/env values in call sites."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class EmbeddingSettings(BaseSettings):
    embedding_model_name: str = "BAAI/bge-large-en-v1.5"
    embedding_device: str = "cpu"
    embedding_dimension: int = 1024
    # Texts per model.encode() call — keeps memory bounded and lets a large
    # document's chunks recover from one failed sub-batch without re-embedding
    # everything already done.
    embedding_batch_size: int = 64
    embedding_max_retries: int = 2

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = EmbeddingSettings()
