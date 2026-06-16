"""Cache store tests."""

import time
from pathlib import Path

from silentinstallhq_mcp.cache import CacheStore


def test_cache_ttl_expiry(tmp_path: Path):
    cache = CacheStore(tmp_path / "cache.sqlite", ttl_seconds=1)
    cache.set("key", {"value": 1})
    assert cache.get("key") == {"value": 1}
    time.sleep(1.1)
    assert cache.get("key") is None