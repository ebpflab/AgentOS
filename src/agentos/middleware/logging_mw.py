"""Structured JSON logging middleware."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class LoggingMiddleware:
    """Structured logging for agent operations.

    Logs request/response with timing, useful for debugging and monitoring.
    """

    def __init__(self, log_level: int = logging.INFO) -> None:
        self._level = log_level

    async def wrap_call(
        self,
        operation: str,
        entity_id: str,
        call_func: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Wrap a call with structured logging."""
        start = time.time()
        logger.log(self._level, "START %s entity=%s", operation, entity_id[:8])

        try:
            result = await call_func(*args, **kwargs)
            duration = time.time() - start
            logger.log(
                self._level,
                "END %s entity=%s duration=%.3fs status=success",
                operation, entity_id[:8], duration,
            )
            return result

        except Exception as e:
            duration = time.time() - start
            logger.log(
                logging.ERROR,
                "END %s entity=%s duration=%.3fs status=error error=%s",
                operation, entity_id[:8], duration, str(e),
            )
            raise
