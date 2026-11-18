from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    # Named app_debug so Windows system env DEBUG=release does not break pydantic
    app_debug: bool = True

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"

    admin_config_service_url: str = "http://localhost:8002"
    retrieval_service_url: str = "http://localhost:8004"

    llm_router_mode: str = "fake"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.3:70b"

    model_config = SettingsConfigDict(
        env_file="../../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
