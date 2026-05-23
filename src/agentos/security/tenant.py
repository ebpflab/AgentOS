"""Tenant isolation context.

Provides TenantContext that scopes all operations to a specific tenant.
Injected by middleware into each request/agent run.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

# Context variable for the current tenant — set by middleware
_current_tenant: ContextVar[TenantContext | None] = ContextVar("current_tenant", default=None)


@dataclass
class TenantContext:
    """Represents the current tenant context for an operation.

    Set by auth middleware and propagated through the request lifecycle.
    Used to scope DB queries, registry lookups, memory access, etc.
    """

    tenant_id: str
    tenant_name: str = ""
    user_id: str = ""
    user_email: str = ""
    roles: list[str] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles


def get_current_tenant() -> TenantContext | None:
    """Get the current tenant context (set by middleware)."""
    return _current_tenant.get()


def set_current_tenant(ctx: TenantContext | None) -> None:
    """Set the current tenant context."""
    _current_tenant.set(ctx)


def require_tenant() -> TenantContext:
    """Get current tenant or raise.

    Raises:
        RuntimeError: If no tenant context is set.
    """
    ctx = _current_tenant.get()
    if ctx is None:
        raise RuntimeError("No tenant context — ensure auth middleware is configured")
    return ctx
