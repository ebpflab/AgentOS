"""Quota definitions and enforcement for multi-tenant resource management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class QuotaDefinition:
    """Resource quotas for a tenant."""

    tenant_id: str
    max_agents: int = 50               # Max agents per tenant
    tokens_per_day: int = 0            # 0 = unlimited
    tokens_per_month: int = 0
    requests_per_minute: int = 60
    cost_per_month_usd: float = 0.0    # 0 = unlimited
    max_sessions: int = 1000
    max_workflows: int = 100


class QuotaManager:
    """Manages per-tenant quotas.

    Usage:
        manager = QuotaManager()
        manager.set_quota("tenant-1", QuotaDefinition(tenant_id="tenant-1", max_agents=10))
        quota = manager.get_quota("tenant-1")
    """

    def __init__(self, default_quota: QuotaDefinition | None = None) -> None:
        self._default = default_quota or QuotaDefinition(tenant_id="__default__")
        self._quotas: dict[str, QuotaDefinition] = {}

    def set_quota(self, tenant_id: str, quota: QuotaDefinition) -> None:
        self._quotas[tenant_id] = quota

    def get_quota(self, tenant_id: str) -> QuotaDefinition:
        return self._quotas.get(tenant_id, self._default)

    def check_agent_limit(self, tenant_id: str, current_count: int) -> bool:
        """Check if tenant can create more agents."""
        quota = self.get_quota(tenant_id)
        return current_count < quota.max_agents

    def to_dict(self, tenant_id: str) -> dict[str, Any]:
        q = self.get_quota(tenant_id)
        return {
            "tenant_id": q.tenant_id,
            "max_agents": q.max_agents,
            "tokens_per_day": q.tokens_per_day,
            "tokens_per_month": q.tokens_per_month,
            "requests_per_minute": q.requests_per_minute,
            "cost_per_month_usd": q.cost_per_month_usd,
            "max_sessions": q.max_sessions,
            "max_workflows": q.max_workflows,
        }
