from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    # Named app_debug so Windows system env DEBUG=release does not break pydantic
    app_debug: bool = True

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None
    qdrant_collection: str = "document_chunks"

    embedding_model_name: str = "fake"
    embedding_device: str = "cpu"
    reranker_model_name: str = "fake"
    reranker_device: str = "cpu"

    # After rerank, best score below this → insufficient_information
    retrieval_score_threshold: float = 0.25
    retrieval_dense_limit: int = 20
    retrieval_lexical_limit: int = 20

    model_config = SettingsConfigDict(
        env_file="../../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
