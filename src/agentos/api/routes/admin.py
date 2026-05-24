"""Admin API routes — tenant, RBAC, and provider management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agentos.api.deps import require_permission
from agentos.api.server import get_runtime
from agentos.security.auth import UserInfo
from agentos.security.rbac import Permission

router = APIRouter()


# ── Tenant ───────────────────────────────────────────────────────

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


# ── Roles ────────────────────────────────────────────────────────

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


# ── Providers ────────────────────────────────────────────────────

class ProviderInfoResponse(BaseModel):
    name: str
    enabled: bool
    default_model: str
    models: list[str]
    api_key_set: bool  # whether an API key is configured (never expose the key)
    base_url: str = ""
    api_base: str = ""


class ProviderUpdateRequest(BaseModel):
    enabled: bool | None = None
    api_key: str | None = None
    default_model: str | None = None
    base_url: str | None = None
    api_base: str | None = None


@router.get("/providers", response_model=list[ProviderInfoResponse])
async def list_providers(
    user: UserInfo = Depends(require_permission(Permission.ADMIN_RBAC)),
):
    """List all configured LLM providers with their status."""
    runtime = get_runtime()
    result: list[ProviderInfoResponse] = []
    for name in runtime.providers.list_providers():
        info = runtime.providers.get_provider_info(name)
        if info is None:
            continue
        # Check if API key is set in config
        cfg = runtime.providers._provider_configs.get(name)
        result.append(ProviderInfoResponse(
            name=info.name,
            enabled=info.enabled,
            default_model=info.default_model,
            models=info.models,
            api_key_set=bool(cfg and cfg.api_key),
            base_url=getattr(cfg, 'base_url', '') or '',
            api_base=getattr(cfg, 'api_base', '') or '',
        ))
    return result


@router.put("/providers/{provider_name}", response_model=ProviderInfoResponse)
async def update_provider(
    provider_name: str,
    req: ProviderUpdateRequest,
    user: UserInfo = Depends(require_permission(Permission.ADMIN_RBAC)),
):
    """Update a provider's configuration.

    Changes apply immediately to new agent starts.
    Existing agents are not affected until restarted.
    """
    runtime = get_runtime()
    try:
        info = runtime.providers.update_provider(
            provider_name,
            enabled=req.enabled,
            api_key=req.api_key,
            default_model=req.default_model,
            base_url=req.base_url,
            api_base=req.api_base,
        )
        cfg = runtime.providers._provider_configs.get(provider_name)
        return ProviderInfoResponse(
            name=info.name,
            enabled=info.enabled,
            default_model=info.default_model,
            models=info.models,
            api_key_set=bool(cfg and cfg.api_key),
            base_url=getattr(cfg, 'base_url', '') or '',
            api_base=getattr(cfg, 'api_base', '') or '',
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Shared Memory ────────────────────────────────────────────────

class SharedMemorySetRequest(BaseModel):
    key: str
    value: str


@router.get("/memory/{namespace}")
async def get_shared_memory(
    namespace: str,
    user: UserInfo = Depends(require_permission(Permission.AGENT_READ)),
):
    """Get all shared memory entries for a namespace (e.g. workflow ID)."""
    runtime = get_runtime()
    return await runtime.shared_memory.get_all(namespace)


@router.post("/memory/{namespace}")
async def set_shared_memory(
    namespace: str,
    req: SharedMemorySetRequest,
    user: UserInfo = Depends(require_permission(Permission.AGENT_CREATE)),
):
    """Set a key-value pair in a shared memory namespace."""
    runtime = get_runtime()
    await runtime.shared_memory.set(namespace, req.key, req.value)
    return {"namespace": namespace, "key": req.key, "ok": True}


@router.delete("/memory/{namespace}/{key}")
async def delete_shared_memory(
    namespace: str,
    key: str,
    user: UserInfo = Depends(require_permission(Permission.AGENT_DELETE)),
):
    """Delete a key from a shared memory namespace."""
    runtime = get_runtime()
    await runtime.shared_memory.delete(namespace, key)
    return {"namespace": namespace, "key": key, "ok": True}
