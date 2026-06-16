"""FastMCP server wiring."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from silentinstallhq_mcp.cache import CacheStore
from silentinstallhq_mcp.config import Settings, get_settings
from silentinstallhq_mcp.http_client import HttpClient
from silentinstallhq_mcp.rate_limiter import RateLimiter
from silentinstallhq_mcp.robots import RobotsChecker
from silentinstallhq_mcp.scraper.client import SilentInstallHQClient
from silentinstallhq_mcp.structured_cache import StructuredCache

logger = logging.getLogger(__name__)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    settings: Settings = server.settings  # type: ignore[attr-defined]
    cache = CacheStore(settings.cache_db_path, settings.cache_ttl_seconds)
    structured_cache = StructuredCache(cache)
    rate_limiter = RateLimiter(settings.request_delay_seconds)
    robots = RobotsChecker(settings, cache, rate_limiter)
    http = HttpClient(settings, cache, rate_limiter)
    http.attach_robots(robots)
    scraper = SilentInstallHQClient(settings, http, structured_cache)

    try:
        yield {"settings": settings, "scraper": scraper, "cache": cache}
    finally:
        await http.close()
        logger.info("HTTP client closed")


def create_mcp(settings: Settings | None = None) -> FastMCP:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    mcp = FastMCP(
        "silentinstallhq",
        instructions=(
            "Query Silent Install HQ for silent install guides, PSADT v4 templates, "
            "command-line switches, uninstall strings, and detection script links."
        ),
        json_response=True,
        stateless_http=True,
        lifespan=app_lifespan,
    )
    mcp.settings = settings  # type: ignore[attr-defined]

    from silentinstallhq_mcp.tools.guides import register_tools

    register_tools(mcp)
    return mcp