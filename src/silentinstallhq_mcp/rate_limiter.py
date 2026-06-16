"""Polite request rate limiting."""

from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Ensures a minimum delay between outbound HTTP requests."""

    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = max(delay_seconds, 0.0)
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0

    async def acquire(self) -> None:
        if self.delay_seconds <= 0:
            return

        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_at
            if elapsed < self.delay_seconds:
                await asyncio.sleep(self.delay_seconds - elapsed)
            self._last_request_at = time.monotonic()