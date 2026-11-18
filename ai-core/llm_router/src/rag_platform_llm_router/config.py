"""LLM router settings — all provider keys/URLs from env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMRouterSettings(BaseSettings):
    # fake | litellm
    llm_router_mode: str = "litellm"

    groq_api_key: str | None = None
    groq_model: str = "groq/llama-3.3-70b-versatile"

    gemini_api_key: str | None = None
    gemini_model: str = "gemini/gemini-1.5-pro"

    openrouter_api_key: str | None = None
    openrouter_model: str = "openrouter/openai/gpt-oss-20b:free"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.3:70b"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = LLMRouterSettings()
