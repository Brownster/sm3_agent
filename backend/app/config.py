from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Centralized configuration for the chat backend."""

    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    mcp_server_url: str = Field("http://localhost:3001/mcp", env="MCP_SERVER_URL")
    model: str = Field("gpt-4o", env="OPENAI_MODEL")
    enable_tracing: bool = Field(False, env="ENABLE_LANGCHAIN_TRACING")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
