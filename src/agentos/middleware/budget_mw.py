"""Token budget enforcement middleware.

Intercepts LLM calls to check budget before and record usage after.
Designed as a MAF @chat_middleware, also works standalone.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

from agentos.resources.budget import BudgetExceededError, BudgetManager

logger = logging.getLogger(__name__)


class BudgetMiddleware:
    """Middleware that enforces token budgets on LLM calls.

    Wraps around agent.run() to:
    1. Check budget before the LLM call
    2. Execute the call
    3. Record token usage from the response

    Also serves as a MAF-compatible chat_middleware when integrated.

    Usage:
        mw = BudgetMiddleware(budget_manager)
        result = await mw.wrap_call(agent_id, call_func, *args)
    """

    def __init__(self, budget_manager: BudgetManager) -> None:
        self._budget = budget_manager

    async def wrap_call(
        self,
        entity_id: str,
        call_func: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Wrap an LLM call with budget checking.

        Args:
            entity_id: Agent or tenant ID to check budget for.
            call_func: The async function to call (e.g., agent.run).
            *args, **kwargs: Arguments to pass to call_func.

        Returns:
            Result from call_func.

        Raises:
            BudgetExceededError: If budget is exhausted.
        """
        # Check budget before call
        self._budget.check(entity_id)

        # Execute the call
        result = await call_func(*args, **kwargs)

        # Record usage (extract from response if available)
        usage = self._extract_usage(result)
        if usage:
            self._budget.record_usage(
                entity_id,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
            )

        return result

    def _extract_usage(self, result: Any) -> dict[str, int] | None:
        """Extract token usage from a response object.

        Attempts to read usage metadata from MAF response objects.
        """
        # Try MAF response metadata patterns
        if hasattr(result, "usage"):
            usage = result.usage
            if hasattr(usage, "input_tokens"):
                return {
                    "input_tokens": getattr(usage, "input_tokens", 0),
                    "output_tokens": getattr(usage, "output_tokens", 0),
                }
        if hasattr(result, "metadata") and isinstance(result.metadata, dict):
            if "usage" in result.metadata:
                return result.metadata["usage"]
        return None

    def check(self, entity_id: str) -> None:
        """Standalone budget check."""
        self._budget.check(entity_id)

    def record(self, entity_id: str, input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Standalone usage recording."""
        self._budget.record_usage(entity_id, input_tokens, output_tokens)
