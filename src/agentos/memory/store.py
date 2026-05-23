"""MemoryStore protocol — unified interface for persistent memory backends.

All backends implement this protocol using structural subtyping.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MemoryStore(Protocol):
    """Protocol for memory storage backends.

    Backends must implement these methods. Uses Python Protocol
    for structural subtyping — no inheritance required.
    """

    async def get(self, key: str, namespace: str = "") -> Any | None:
        """Retrieve a value by key."""
        ...

    async def set(self, key: str, value: Any, namespace: str = "", ttl: int | None = None) -> None:
        """Store a value with optional TTL (seconds)."""
        ...

    async def delete(self, key: str, namespace: str = "") -> bool:
        """Delete a key. Returns True if existed."""
        ...

    async def list_keys(self, namespace: str = "", prefix: str = "") -> list[str]:
        """List keys in a namespace, optionally filtered by prefix."""
        ...

    async def search(self, query: str, namespace: str = "", limit: int = 10) -> list[dict[str, Any]]:
        """Search for entries matching a query (text or vector similarity)."""
        ...

    async def exists(self, key: str, namespace: str = "") -> bool:
        """Check if a key exists."""
        ...
