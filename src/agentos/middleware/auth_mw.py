"""Authentication middleware for FastAPI and MAF agents.

Validates JWT tokens from the Authorization header and sets up TenantContext.
"""

from __future__ import annotations

import logging
from typing import Any

from agentos.security.auth import AuthProvider, AuthenticationError, UserInfo
from agentos.security.tenant import TenantContext, set_current_tenant

logger = logging.getLogger(__name__)


class AuthMiddleware:
    """Middleware that validates authentication and sets tenant context.

    For FastAPI integration:
        async def get_current_user(request: Request) -> UserInfo:
            return await auth_mw.authenticate(request.headers.get("Authorization", ""))

    For MAF agent_middleware:
        Applied as a decorator to intercept agent runs.
    """

    def __init__(self, auth_provider: AuthProvider, require_auth: bool = True) -> None:
        self._auth = auth_provider
        self._require_auth = require_auth

    async def authenticate(self, authorization: str | None) -> UserInfo:
        """Validate authorization header and return user info.

        Args:
            authorization: "Bearer <token>" or None.

        Returns:
            UserInfo with user/tenant claims.

        Raises:
            AuthenticationError: If auth required and token invalid.
        """
        if not authorization:
            if self._require_auth:
                raise AuthenticationError("Authorization header required")
            return self._auth.create_dev_user()

        user = await self._auth.validate_token(authorization)

        # Set tenant context for the current request
        set_current_tenant(TenantContext(
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            user_email=user.email,
            roles=user.roles,
        ))

        return user

    async def authenticate_or_default(self, authorization: str | None) -> UserInfo:
        """Authenticate or return default dev user (for development mode)."""
        try:
            return await self.authenticate(authorization)
        except AuthenticationError:
            if not self._require_auth:
                return self._auth.create_dev_user()
            raise
