"""Application configuration."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="SILENTINSTALLHQ_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    transport: str = Field(
        default="stdio",
        description="MCP transport: stdio, sse, streamable-http",
    )
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    cache_dir: Path = Field(default=Path("./data"))
    cache_ttl_hours: int = Field(default=24)

    base_url: str = Field(default="https://silentinstallhq.com")
    user_agent: str = Field(
        default=(
            "mcp-server-silentinstallhq/0.1.0 "
            "(+https://github.com/perezdap/mcp-server-silentinstallhq; MCP research bot)"
        )
    )
    request_delay_seconds: float = Field(default=1.0)
    request_timeout_seconds: float = Field(default=30.0)
    respect_robots_txt: bool = Field(default=True)
    httpx_max_connections: int = Field(default=5)
    httpx_max_keepalive_connections: int = Field(default=2)

    log_level: str = Field(default="INFO")

    @property
    def cache_db_path(self) -> Path:
        return self.cache_dir / "cache.sqlite"

    @property
    def cache_ttl_seconds(self) -> int:
        return self.cache_ttl_hours * 3600


def get_settings() -> Settings:
    return Settings()