from functools import lru_cache
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized configuration for the chat backend."""

    # Required settings
    openai_api_key: str = Field(..., env="OPENAI_API_KEY", description="OpenAI API key for LLM")

    # MCP Server configuration
    mcp_server_url: str = Field(
        "http://localhost:3001/mcp",
        env="MCP_SERVER_URL",
        description="URL of the Grafana MCP server"
    )

    # LLM configuration
    model: str = Field("gpt-4o", env="OPENAI_MODEL", description="OpenAI model to use")
    enable_tracing: bool = Field(
        False,
        env="ENABLE_LANGCHAIN_TRACING",
        description="Enable LangChain tracing for debugging"
    )

    # CORS configuration
    cors_origins: Union[str, List[str]] = Field(
        default="http://localhost:3000,http://localhost:8001",
        env="CORS_ORIGINS",
        description="Allowed CORS origins (comma-separated string or list)"
    )
    cors_allow_credentials: bool = Field(
        True,
        env="CORS_ALLOW_CREDENTIALS",
        description="Allow credentials in CORS requests"
    )

    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_api_key(cls, v: str) -> str:
        """Validate that OpenAI API key is not empty."""
        if not v or v.strip() == "":
            raise ValueError("OPENAI_API_KEY must be set and not empty")
        if not v.startswith("sk-"):
            raise ValueError("OPENAI_API_KEY must start with 'sk-'")
        return v

    @field_validator("mcp_server_url")
    @classmethod
    def validate_mcp_server_url(cls, v: str) -> str:
        """Validate that MCP server URL is a valid HTTP(S) URL."""
        if not v or v.strip() == "":
            raise ValueError("MCP_SERVER_URL must be set and not empty")
        if not v.startswith(("http://", "https://")):
            raise ValueError("MCP_SERVER_URL must start with http:// or https://")
        return v

    @field_validator("cors_origins", mode="after")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            # Split by comma and strip whitespace
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Disable JSON parsing for complex types from env vars
        env_parse_enums=True,
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance with validation."""
    return Settings()
