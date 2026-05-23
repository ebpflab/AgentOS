"""Admin API routes — tenant and RBAC management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agentos.api.deps import require_permission
from agentos.security.auth import UserInfo
from agentos.security.rbac import Permission

router = APIRouter()


class TenantCreateRequest(BaseModel):
    name: str
    display_name: str = ""


class TenantResponse(BaseModel):
    tenant_id: str
    name: str
    display_name: str = ""
    is_active: bool = True


@router.get("/tenants", response_model=list[TenantResponse])
async def list_tenants(
    user: UserInfo = Depends(require_permission(Permission.ADMIN_TENANTS)),
):
    """List all tenants."""
    return []  # Populated when DB integration is active


@router.post("/tenants", response_model=TenantResponse, status_code=201)
async def create_tenant(
    req: TenantCreateRequest,
    user: UserInfo = Depends(require_permission(Permission.ADMIN_TENANTS)),
):
    """Create a new tenant."""
    from uuid import uuid4
    return TenantResponse(
        tenant_id=str(uuid4())[:8],
        name=req.name,
        display_name=req.display_name,
    )


@router.get("/roles")
async def list_roles(
    user: UserInfo = Depends(require_permission(Permission.ADMIN_RBAC)),
):
    """List available roles and their permissions."""
    from agentos.security.rbac import DEFAULT_ROLE_PERMISSIONS
    return {
        role: [p.value for p in perms]
        for role, perms in DEFAULT_ROLE_PERMISSIONS.items()
    }
