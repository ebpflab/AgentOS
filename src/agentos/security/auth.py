"""OAuth2/OIDC SSO integration for enterprise authentication.

Supports Azure AD, Okta, Keycloak, and any OIDC-compliant provider.
Validates JWT tokens and extracts user/tenant claims.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class UserInfo:
    """Authenticated user information extracted from JWT."""

    user_id: str
    email: str = ""
    name: str = ""
    tenant_id: str = "default"
    roles: list[str] = field(default_factory=list)
    claims: dict[str, Any] = field(default_factory=dict)


@dataclass
class OIDCConfig:
    """OIDC provider configuration."""

    issuer_url: str
    client_id: str
    client_secret: str = ""
    audience: str = ""
    # Claim mappings
    tenant_claim: str = "tenant_id"   # JWT claim for tenant ID
    roles_claim: str = "roles"         # JWT claim for roles
    email_claim: str = "email"
    name_claim: str = "name"


class AuthProvider:
    """Handles JWT validation and user info extraction.

    In production, this validates tokens against the OIDC discovery endpoint.
    For development, supports a simple API key mode.

    Usage:
        auth = AuthProvider(oidc_config)
        await auth.initialize()
        user = await auth.validate_token("Bearer eyJ...")
    """

    def __init__(self, config: OIDCConfig | None = None) -> None:
        self._config = config
        self._jwks: dict[str, Any] | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Fetch OIDC discovery document and JWKS keys."""
        if not self._config or not self._config.issuer_url:
            logger.info("No OIDC config — auth disabled, using default user")
            self._initialized = True
            return

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                # Fetch OIDC discovery
                discovery_url = f"{self._config.issuer_url.rstrip('/')}/.well-known/openid-configuration"
                resp = await client.get(discovery_url)
                resp.raise_for_status()
                discovery = resp.json()

                # Fetch JWKS
                jwks_url = discovery["jwks_uri"]
                resp = await client.get(jwks_url)
                resp.raise_for_status()
                self._jwks = resp.json()

            self._initialized = True
            logger.info("OIDC initialized from %s", self._config.issuer_url)

        except Exception:
            logger.exception("Failed to initialize OIDC from %s", self._config.issuer_url)
            # Allow startup even if OIDC fails — auth will reject all tokens
            self._initialized = True

    async def validate_token(self, authorization: str) -> UserInfo:
        """Validate a Bearer token and extract user info.

        Args:
            authorization: "Bearer <token>" header value.

        Returns:
            UserInfo with extracted claims.

        Raises:
            AuthenticationError: If token is invalid.
        """
        if not authorization.startswith("Bearer "):
            raise AuthenticationError("Invalid authorization header format")

        token = authorization[7:]

        if not self._config or not self._config.issuer_url:
            # No OIDC configured — return default user (dev mode)
            return UserInfo(user_id="dev-user", tenant_id="default", roles=["admin"])

        try:
            from jose import jwt as jose_jwt

            payload = jose_jwt.decode(
                token,
                self._jwks,
                algorithms=["RS256"],
                audience=self._config.audience or self._config.client_id,
                issuer=self._config.issuer_url,
            )

            return UserInfo(
                user_id=payload.get("sub", ""),
                email=payload.get(self._config.email_claim, ""),
                name=payload.get(self._config.name_claim, ""),
                tenant_id=payload.get(self._config.tenant_claim, "default"),
                roles=payload.get(self._config.roles_claim, []),
                claims=payload,
            )

        except Exception as e:
            raise AuthenticationError(f"Token validation failed: {e}") from e

    def create_dev_user(self, user_id: str = "dev-user", tenant_id: str = "default") -> UserInfo:
        """Create a development user (no token validation)."""
        return UserInfo(
            user_id=user_id,
            email=f"{user_id}@dev.local",
            name="Development User",
            tenant_id=tenant_id,
            roles=["admin"],
        )


class AuthenticationError(Exception):
    """Raised when authentication fails."""
