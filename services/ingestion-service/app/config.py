from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    # Named app_debug so Windows system env DEBUG=release does not break pydantic
    app_debug: bool = True

    database_url: str
    # Sync URL for Celery worker (psycopg2)
    database_url_sync: str | None = None

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None
    qdrant_collection: str = "document_chunks"

    # local | s3
    storage_backend: str = "local"
    local_storage_path: str = "./data/object-storage"
    s3_endpoint: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket: str = "rag-platform-documents"
    s3_region: str = "auto"

    embedding_model_name: str = "fake"
    embedding_device: str = "cpu"

    # Local default True: index in-process (no separate Celery worker). Set 0 in prod.
    celery_task_always_eager: bool = True

    model_config = SettingsConfigDict(
        env_file="../../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @property
    def sync_database_url(self) -> str:
        if self.database_url_sync:
            return self.database_url_sync
        # Derive sync URL from asyncpg URL
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")


settings = Settings()
