"""Authentication API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agentos.api.server import get_runtime
from agentos.i18n import get_locale, tr

router = APIRouter()


class LoginRequest(BaseModel):
    username: str = ""
    password: str = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str = ""
    roles: list[str] = []


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, locale: str = Depends(get_locale)):
    """Login endpoint (dev mode returns a dev token)."""
    runtime = get_runtime()
    if not runtime.config.security.auth_enabled:
        return TokenResponse(
            access_token="dev-token",
            tenant_id=runtime.config.security.default_tenant,
            roles=["admin"],
        )
    raise HTTPException(status_code=501, detail=tr("auth.use_oidc", locale))


@router.get("/callback")
async def oidc_callback(code: str = "", state: str = "", locale: str = Depends(get_locale)):
    """OIDC callback endpoint for SSO."""
    # In production, exchange code for tokens
    return {"status": tr("auth.callback_received", locale), "code": code[:10] + "..."}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str = "", locale: str = Depends(get_locale)):
    """Refresh an access token."""
    raise HTTPException(status_code=501, detail=tr("auth.refresh_not_impl", locale))
