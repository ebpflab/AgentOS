"""Dependency injection helpers for FastAPI routes."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from agentos.api.server import get_runtime
from agentos.kernel.runtime import AgentOSRuntime
from agentos.security.auth import AuthenticationError, UserInfo
from agentos.security.rbac import AccessDeniedError, Permission, RBACManager
from agentos.security.tenant import TenantContext, set_current_tenant

_rbac = RBACManager()


async def get_current_user(
    authorization: str | None = Header(None),
) -> UserInfo:
    """Extract user from Authorization header.

    In dev mode (auth_enabled=False), returns a default admin user.
    """
    runtime = get_runtime()

    if not runtime.config.security.auth_enabled:
        user = UserInfo(
            user_id="dev-user",
            email="dev@local",
            name="Developer",
            tenant_id=runtime.config.security.default_tenant,
            roles=["admin"],
        )
        set_current_tenant(TenantContext(
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            roles=user.roles,
        ))
        return user

    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization required")

    try:
        from agentos.security.auth import AuthProvider
        auth = AuthProvider()
        await auth.initialize()
        user = await auth.validate_token(authorization)
        set_current_tenant(TenantContext(
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            roles=user.roles,
        ))
        return user
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


def require_permission(permission: Permission):
    """Dependency that checks a specific permission."""

    async def _check(user: UserInfo = Depends(get_current_user)) -> UserInfo:
        try:
            _rbac.check(user.user_id, user.roles, permission)
        except AccessDeniedError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        return user

    return _check
