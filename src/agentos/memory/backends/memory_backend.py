"""In-memory backend for development and testing."""

from __future__ import annotations

import time
from typing import Any


class InMemoryBackend:
    """Simple in-memory storage backend.

    Implements the MemoryStore protocol. Supports TTL expiration.
    Data is lost on process restart — use only for dev/testing.
    """

    def __init__(self) -> None:
        # namespace -> key -> (value, expire_at | None)
        self._data: dict[str, dict[str, tuple[Any, float | None]]] = {}

    def _ns(self, namespace: str) -> dict[str, tuple[Any, float | None]]:
        if namespace not in self._data:
            self._data[namespace] = {}
        return self._data[namespace]

    def _is_expired(self, entry: tuple[Any, float | None]) -> bool:
        _, expire_at = entry
        return expire_at is not None and time.time() > expire_at

    async def get(self, key: str, namespace: str = "") -> Any | None:
        ns = self._ns(namespace)
        entry = ns.get(key)
        if entry is None:
            return None
        if self._is_expired(entry):
            del ns[key]
            return None
        return entry[0]

    async def set(self, key: str, value: Any, namespace: str = "", ttl: int | None = None) -> None:
        expire_at = (time.time() + ttl) if ttl else None
        self._ns(namespace)[key] = (value, expire_at)

    async def delete(self, key: str, namespace: str = "") -> bool:
        ns = self._ns(namespace)
        if key in ns:
            del ns[key]
            return True
        return False

    async def list_keys(self, namespace: str = "", prefix: str = "") -> list[str]:
        ns = self._ns(namespace)
        now = time.time()
        keys = []
        expired = []
        for k, entry in ns.items():
            if self._is_expired(entry):
                expired.append(k)
                continue
            if prefix and not k.startswith(prefix):
                continue
            keys.append(k)
        for k in expired:
            del ns[k]
        return keys

    async def search(self, query: str, namespace: str = "", limit: int = 10) -> list[dict[str, Any]]:
        """Simple substring search (no vector search in-memory)."""
        ns = self._ns(namespace)
        results = []
        query_lower = query.lower()
        for key, entry in ns.items():
            if self._is_expired(entry):
                continue
            value = entry[0]
            value_str = str(value).lower()
            if query_lower in key.lower() or query_lower in value_str:
                results.append({"key": key, "value": value, "score": 1.0})
            if len(results) >= limit:
                break
        return results

    async def exists(self, key: str, namespace: str = "") -> bool:
        ns = self._ns(namespace)
        entry = ns.get(key)
        if entry is None:
            return False
        if self._is_expired(entry):
            del ns[key]
            return False
        return True

    def clear(self, namespace: str | None = None) -> None:
        """Clear all data or a specific namespace."""
        if namespace is None:
            self._data.clear()
        else:
            self._data.pop(namespace, None)
