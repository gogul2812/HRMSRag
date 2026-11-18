from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    # Named app_debug so Windows system env DEBUG=release does not break pydantic
    app_debug: bool = True
    
    # Redis
    redis_url: str
    
    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    
    # Downstream service URLs
    auth_service_url: str = "http://localhost:8001"
    admin_config_service_url: str = "http://localhost:8002"
    ingestion_service_url: str = "http://localhost:8003"
    retrieval_service_url: str = "http://localhost:8004"
    llm_orchestrator_service_url: str = "http://localhost:8005"
    chat_service_url: str = "http://localhost:8006"
    notification_service_url: str = "http://localhost:8007"

    model_config = SettingsConfigDict(env_file="../../.env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
