"""robots.txt enforcement tests."""

import pytest

from silentinstallhq_mcp.cache import CacheStore
from silentinstallhq_mcp.config import Settings
from silentinstallhq_mcp.rate_limiter import RateLimiter
from silentinstallhq_mcp.robots import RobotsChecker, RobotsDisallowedError


@pytest.fixture
def robots_checker(tmp_path) -> RobotsChecker:
    settings = Settings(
        base_url="https://silentinstallhq.com",
        respect_robots_txt=True,
        request_delay_seconds=0,
    )
    cache = CacheStore(tmp_path / "cache.sqlite", ttl_seconds=3600)
    return RobotsChecker(settings, cache, RateLimiter(0))


@pytest.mark.asyncio
async def test_robots_allows_public_guide_paths(robots_checker: RobotsChecker):
    robots_body = """
User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php
"""
    robots_checker.cache.set(robots_checker._cache_key(), robots_body)
    await robots_checker.check_allowed("https://silentinstallhq.com/cisco-proximity-silent-install-how-to-guide/")


@pytest.mark.asyncio
async def test_robots_blocks_disallowed_paths(robots_checker: RobotsChecker):
    robots_body = """
User-agent: *
Disallow: /wp-admin/
"""
    robots_checker.cache.set(robots_checker._cache_key(), robots_body)
    with pytest.raises(RobotsDisallowedError):
        await robots_checker.check_allowed("https://silentinstallhq.com/wp-admin/index.php")


@pytest.mark.asyncio
async def test_robots_can_be_disabled(robots_checker: RobotsChecker):
    robots_checker.settings = Settings(
        base_url="https://silentinstallhq.com",
        respect_robots_txt=False,
    )
    robots_checker.cache.set(
        robots_checker._cache_key(),
        "User-agent: *\nDisallow: /\n",
    )
    await robots_checker.check_allowed("https://silentinstallhq.com/anything")