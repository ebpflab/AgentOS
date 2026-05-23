"""Credential vault — abstracts secret storage.

Supports environment variables (default), config files, and Azure Key Vault.
Never exposes secrets in agent context or logs.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class CredentialVault(Protocol):
    """Protocol for credential storage backends."""

    async def get_secret(self, name: str) -> str | None: ...
    async def set_secret(self, name: str, value: str) -> None: ...


class EnvCredentialVault:
    """Loads credentials from environment variables.

    Convention: secrets are stored as AGENTOS_SECRET_{NAME} in uppercase.
    """

    def __init__(self, prefix: str = "AGENTOS_SECRET_") -> None:
        self._prefix = prefix

    async def get_secret(self, name: str) -> str | None:
        env_key = f"{self._prefix}{name.upper()}"
        value = os.environ.get(env_key)
        if value:
            logger.debug("Retrieved secret '%s' from env", name)
        return value

    async def set_secret(self, name: str, value: str) -> None:
        env_key = f"{self._prefix}{name.upper()}"
        os.environ[env_key] = value
        logger.debug("Set secret '%s' in env", name)


class ConfigCredentialVault:
    """Loads credentials from a config dictionary (for testing)."""

    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        self._secrets = dict(secrets or {})

    async def get_secret(self, name: str) -> str | None:
        return self._secrets.get(name)

    async def set_secret(self, name: str, value: str) -> None:
        self._secrets[name] = value


class CompositeCredentialVault:
    """Tries multiple vaults in order until a secret is found."""

    def __init__(self, vaults: list[Any]) -> None:
        self._vaults = vaults

    async def get_secret(self, name: str) -> str | None:
        for vault in self._vaults:
            value = await vault.get_secret(name)
            if value is not None:
                return value
        return None

    async def set_secret(self, name: str, value: str) -> None:
        # Write to the first vault
        if self._vaults:
            await self._vaults[0].set_secret(name, value)
