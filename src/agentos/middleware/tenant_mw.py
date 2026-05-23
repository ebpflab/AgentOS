"""Tenant context injection middleware."""

from __future__ import annotations

from agentos.security.tenant import TenantContext, set_current_tenant


class TenantMiddleware:
    """Injects tenant context for scoping operations.

    Used by MAF agent_middleware to set tenant context before agent runs.
    """

    async def inject(self, tenant_id: str, user_id: str = "", roles: list[str] | None = None) -> TenantContext:
        """Set up tenant context for the current operation."""
        ctx = TenantContext(
            tenant_id=tenant_id,
            user_id=user_id,
            roles=roles or [],
        )
        set_current_tenant(ctx)
        return ctx
