"""Token budget manager — per-agent and per-tenant token limit tracking.

Tracks token usage and enforces configurable budgets.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    """Raised when a token budget is exhausted."""


@dataclass
class BudgetRecord:
    """Tracks token usage against a budget."""

    entity_id: str            # agent_id or tenant_id
    entity_type: str          # "agent" or "tenant"
    budget_tokens: int        # 0 = unlimited
    used_tokens: int = 0
    used_input_tokens: int = 0
    used_output_tokens: int = 0
    request_count: int = 0

    @property
    def remaining(self) -> int:
        if self.budget_tokens == 0:
            return -1  # Unlimited
        return max(0, self.budget_tokens - self.used_tokens)

    @property
    def is_exceeded(self) -> bool:
        if self.budget_tokens == 0:
            return False
        return self.used_tokens >= self.budget_tokens

    @property
    def usage_percent(self) -> float:
        if self.budget_tokens == 0:
            return 0.0
        return min(100.0, (self.used_tokens / self.budget_tokens) * 100)


class BudgetManager:
    """Manages token budgets for agents and tenants.

    Usage:
        manager = BudgetManager(default_budget=100000)
        manager.set_budget("agent-1", "agent", 50000)
        manager.check("agent-1")       # Raises BudgetExceededError if over
        manager.record_usage("agent-1", input_tokens=100, output_tokens=50)
    """

    def __init__(self, default_budget: int = 0) -> None:
        self._default_budget = default_budget
        self._records: dict[str, BudgetRecord] = {}

    def set_budget(self, entity_id: str, entity_type: str = "agent", budget_tokens: int = 0) -> BudgetRecord:
        """Set or update a budget for an entity."""
        if entity_id in self._records:
            self._records[entity_id].budget_tokens = budget_tokens
        else:
            self._records[entity_id] = BudgetRecord(
                entity_id=entity_id,
                entity_type=entity_type,
                budget_tokens=budget_tokens,
            )
        return self._records[entity_id]

    def get_record(self, entity_id: str) -> BudgetRecord:
        """Get or create a budget record."""
        if entity_id not in self._records:
            self._records[entity_id] = BudgetRecord(
                entity_id=entity_id,
                entity_type="agent",
                budget_tokens=self._default_budget,
            )
        return self._records[entity_id]

    def check(self, entity_id: str) -> None:
        """Check if an entity has budget remaining.

        Raises:
            BudgetExceededError: If budget is exhausted.
        """
        record = self.get_record(entity_id)
        if record.is_exceeded:
            raise BudgetExceededError(
                f"Token budget exceeded for {record.entity_type} '{entity_id}': "
                f"used {record.used_tokens}/{record.budget_tokens} tokens"
            )

    def record_usage(
        self,
        entity_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> BudgetRecord:
        """Record token usage for an entity."""
        record = self.get_record(entity_id)
        record.used_input_tokens += input_tokens
        record.used_output_tokens += output_tokens
        record.used_tokens += input_tokens + output_tokens
        record.request_count += 1
        return record

    def get_usage_summary(self, entity_id: str) -> dict[str, Any]:
        """Get usage summary for an entity."""
        record = self.get_record(entity_id)
        return {
            "entity_id": entity_id,
            "entity_type": record.entity_type,
            "budget_tokens": record.budget_tokens,
            "used_tokens": record.used_tokens,
            "remaining": record.remaining,
            "usage_percent": record.usage_percent,
            "request_count": record.request_count,
        }

    def reset(self, entity_id: str) -> None:
        """Reset usage counters (e.g., for a new billing period)."""
        record = self.get_record(entity_id)
        record.used_tokens = 0
        record.used_input_tokens = 0
        record.used_output_tokens = 0
        record.request_count = 0

    def list_records(self) -> list[BudgetRecord]:
        return list(self._records.values())
