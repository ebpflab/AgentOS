"""Metrics and cost analytics API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from agentos.api.deps import require_permission
from agentos.api.server import get_runtime
from agentos.security.auth import UserInfo
from agentos.security.rbac import Permission

router = APIRouter()


@router.get("/agents")
async def agent_metrics(
    user: UserInfo = Depends(require_permission(Permission.METRICS_READ)),
):
    """Get agent-level metrics."""
    runtime = get_runtime()
    agents = runtime.registry.list_agents(tenant_id=user.tenant_id)
    return {
        "total_agents": len(agents),
        "by_status": _count_by_status(agents),
        "by_provider": _count_by_field(agents, "provider"),
    }


@router.get("/cost")
async def cost_metrics(
    period: str = "7d",
    user: UserInfo = Depends(require_permission(Permission.METRICS_READ)),
):
    """Get cost analytics."""
    return {
        "tenant_id": user.tenant_id,
        "period": period,
        "total_cost_usd": 0.0,
        "by_agent": [],
        "by_model": [],
    }


@router.get("/tokens")
async def token_metrics(
    user: UserInfo = Depends(require_permission(Permission.METRICS_READ)),
):
    """Get token usage metrics."""
    return {
        "tenant_id": user.tenant_id,
        "total_tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "request_count": 0,
    }


def _count_by_status(agents):
    counts = {}
    for a in agents:
        s = a.status.value
        counts[s] = counts.get(s, 0) + 1
    return counts


def _count_by_field(agents, field):
    counts = {}
    for a in agents:
        v = getattr(a, field, "") or "unknown"
        counts[v] = counts.get(v, 0) + 1
    return counts
