"""HTTP client with caching, rate limiting, robots.txt, and polite headers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from silentinstallhq_mcp.cache import CacheStore
from silentinstallhq_mcp.config import Settings
from silentinstallhq_mcp.rate_limiter import RateLimiter
from silentinstallhq_mcp.robots import RobotsDisallowedError

if TYPE_CHECKING:
    from silentinstallhq_mcp.robots import RobotsChecker

logger = logging.getLogger(__name__)


class ScrapeError(Exception):
    """Raised when a scrape request fails."""


class HttpClient:
    """Thin wrapper around httpx with cache and rate limiting."""

    def __init__(
        self,
        settings: Settings,
        cache: CacheStore,
        rate_limiter: RateLimiter,
        robots: RobotsChecker | None = None,
    ) -> None:
        self.settings = settings
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.robots = robots
        limits = httpx.Limits(
            max_connections=settings.httpx_max_connections,
            max_keepalive_connections=settings.httpx_max_keepalive_connections,
        )
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml",
            },
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
            limits=limits,
        )

    def attach_robots(self, robots: RobotsChecker) -> None:
        self.robots = robots

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_html(self, url: str, *, use_cache: bool = True) -> tuple[str, bool]:
        """Return HTML and whether the response came from cache."""
        if self.robots is not None:
            try:
                await self.robots.check_allowed(url)
            except RobotsDisallowedError as exc:
                raise ScrapeError(str(exc)) from exc

        cache_key = f"html:{url}"
        if use_cache:
            cached = self.cache.get(cache_key)
            if isinstance(cached, str):
                logger.debug("HTML cache hit for %s", url)
                return cached, True

        await self.rate_limiter.acquire()
        logger.info("Fetching %s", url)

        try:
            response = await self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ScrapeError(f"HTTP {exc.response.status_code} for {url}") from exc
        except httpx.HTTPError as exc:
            raise ScrapeError(f"Request failed for {url}: {exc}") from exc

        html = response.text
        if use_cache:
            self.cache.set(cache_key, html)
        return html, False