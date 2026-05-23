"""Sliding window rate limiter for per-agent/tenant request throttling."""

from __future__ import annotations

import time
from collections import defaultdict


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded."""


class RateLimiter:
    """Sliding window rate limiter.

    Tracks requests per entity within a time window.

    Usage:
        limiter = RateLimiter(max_requests=60, window_seconds=60)
        limiter.check("agent-1")  # Raises RateLimitExceededError if over limit
        limiter.record("agent-1")
    """

    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0) -> None:
        self._max_requests = max_requests
        self._window = window_seconds
        self._timestamps: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, entity_id: str) -> None:
        """Remove expired timestamps."""
        cutoff = time.time() - self._window
        self._timestamps[entity_id] = [
            ts for ts in self._timestamps[entity_id] if ts > cutoff
        ]

    def check(self, entity_id: str) -> None:
        """Check if entity is within rate limit.

        Raises:
            RateLimitExceededError: If limit exceeded.
        """
        if self._max_requests <= 0:
            return  # Unlimited

        self._cleanup(entity_id)
        current_count = len(self._timestamps[entity_id])

        if current_count >= self._max_requests:
            raise RateLimitExceededError(
                f"Rate limit exceeded for '{entity_id}': "
                f"{current_count}/{self._max_requests} requests in {self._window}s window"
            )

    def record(self, entity_id: str) -> int:
        """Record a request for an entity.

        Returns:
            Current request count in the window.
        """
        self._cleanup(entity_id)
        self._timestamps[entity_id].append(time.time())
        return len(self._timestamps[entity_id])

    def check_and_record(self, entity_id: str) -> int:
        """Check limit and record in one call.

        Returns:
            Current request count after recording.
        """
        self.check(entity_id)
        return self.record(entity_id)

    def get_remaining(self, entity_id: str) -> int:
        """Get remaining requests allowed in current window."""
        if self._max_requests <= 0:
            return -1
        self._cleanup(entity_id)
        return max(0, self._max_requests - len(self._timestamps[entity_id]))

    def reset(self, entity_id: str) -> None:
        """Reset rate limit counters for an entity."""
        self._timestamps.pop(entity_id, None)
