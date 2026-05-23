"""Shared Knowledge Base — namespace-scoped persistent memory.

Provides a shared knowledge store where agents can read/write facts,
scoped by tenant and optionally by agent.

Namespace convention:
    {tenant_id}/shared/{key}     — shared across all agents in tenant
    {tenant_id}/{agent_id}/{key} — private to a specific agent
"""

from __future__ import annotations

import logging
from typing import Any

from agentos.memory.store import MemoryStore

logger = logging.getLogger(__name__)


class SharedKnowledgeBase:
    """Namespace-scoped knowledge base built on top of a MemoryStore backend.

    Usage:
        kb = SharedKnowledgeBase(backend)
        await kb.set_shared("tenant-1", "company_info", {"name": "Acme"})
        await kb.set_agent("tenant-1", "agent-1", "user_prefs", {"theme": "dark"})

        info = await kb.get_shared("tenant-1", "company_info")
        prefs = await kb.get_agent("tenant-1", "agent-1", "user_prefs")
    """

    def __init__(self, backend: MemoryStore) -> None:
        self._backend = backend

    # --- Shared (tenant-wide) ---

    async def get_shared(self, tenant_id: str, key: str) -> Any | None:
        ns = f"{tenant_id}/shared"
        return await self._backend.get(key, namespace=ns)

    async def set_shared(self, tenant_id: str, key: str, value: Any, ttl: int | None = None) -> None:
        ns = f"{tenant_id}/shared"
        await self._backend.set(key, value, namespace=ns, ttl=ttl)

    async def delete_shared(self, tenant_id: str, key: str) -> bool:
        ns = f"{tenant_id}/shared"
        return await self._backend.delete(key, namespace=ns)

    async def list_shared(self, tenant_id: str, prefix: str = "") -> list[str]:
        ns = f"{tenant_id}/shared"
        return await self._backend.list_keys(namespace=ns, prefix=prefix)

    async def search_shared(self, tenant_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        ns = f"{tenant_id}/shared"
        return await self._backend.search(query, namespace=ns, limit=limit)

    # --- Agent-scoped (private to an agent) ---

    async def get_agent(self, tenant_id: str, agent_id: str, key: str) -> Any | None:
        ns = f"{tenant_id}/{agent_id}"
        return await self._backend.get(key, namespace=ns)

    async def set_agent(
        self, tenant_id: str, agent_id: str, key: str, value: Any, ttl: int | None = None
    ) -> None:
        ns = f"{tenant_id}/{agent_id}"
        await self._backend.set(key, value, namespace=ns, ttl=ttl)

    async def delete_agent(self, tenant_id: str, agent_id: str, key: str) -> bool:
        ns = f"{tenant_id}/{agent_id}"
        return await self._backend.delete(key, namespace=ns)

    async def list_agent_keys(self, tenant_id: str, agent_id: str, prefix: str = "") -> list[str]:
        ns = f"{tenant_id}/{agent_id}"
        return await self._backend.list_keys(namespace=ns, prefix=prefix)

    # --- Convenience ---

    async def get_any(self, tenant_id: str, agent_id: str, key: str) -> Any | None:
        """Get a value, checking agent-scoped first, then shared."""
        result = await self.get_agent(tenant_id, agent_id, key)
        if result is not None:
            return result
        return await self.get_shared(tenant_id, key)
