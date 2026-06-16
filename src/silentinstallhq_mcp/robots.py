"""robots.txt fetching and enforcement."""

from __future__ import annotations

import logging
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import httpx

from silentinstallhq_mcp.cache import CacheStore
from silentinstallhq_mcp.config import Settings
from silentinstallhq_mcp.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class RobotsDisallowedError(Exception):
    """Raised when robots.txt disallows fetching a URL."""


class RobotsChecker:
    """Loads robots.txt and validates outbound scrape targets."""

    def __init__(
        self,
        settings: Settings,
        cache: CacheStore,
        rate_limiter: RateLimiter,
    ) -> None:
        self.settings = settings
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.base_url = settings.base_url.rstrip("/")
        self._parser = RobotFileParser()
        self._loaded = False

    @property
    def robots_url(self) -> str:
        return urljoin(f"{self.base_url}/", "robots.txt")

    def _cache_key(self) -> str:
        return f"robots:{self.base_url}"

    async def _load(self) -> None:
        if self._loaded:
            return

        cached = self.cache.get(self._cache_key())
        if isinstance(cached, str):
            self._parser.parse(cached.splitlines())
            self._loaded = True
            logger.debug("Loaded robots.txt from cache for %s", self.base_url)
            return

        await self.rate_limiter.acquire()
        logger.info("Fetching robots.txt from %s", self.robots_url)

        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": self.settings.user_agent},
                timeout=self.settings.request_timeout_seconds,
                follow_redirects=True,
            ) as client:
                response = await client.get(self.robots_url)
                response.raise_for_status()
                body = response.text
        except httpx.HTTPError as exc:
            logger.warning("robots.txt fetch failed (%s); allowing requests by default", exc)
            self._parser.parse([])
            self._loaded = True
            return

        self.cache.set(self._cache_key(), body)
        self._parser.parse(body.splitlines())
        self._loaded = True

    async def check_allowed(self, url: str) -> None:
        if not self.settings.respect_robots_txt:
            return

        await self._load()
        if self._parser.can_fetch(self.settings.user_agent, url):
            return

        raise RobotsDisallowedError(
            f"robots.txt disallows fetching {url} for User-Agent {self.settings.user_agent!r}"
        )