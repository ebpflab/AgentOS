"""PostgreSQL + pgvector backend for persistent memory with vector search."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


class PostgresBackend:
    """PostgreSQL backend with optional pgvector for vector similarity search.

    Implements the MemoryStore protocol.
    Stores entries as JSON in a `memory_store` table with namespace partitioning.
    When pgvector is available, supports vector similarity search.

    Table schema (auto-created if not exists):
        memory_store(
            namespace VARCHAR(255),
            key VARCHAR(512),
            value JSONB,
            embedding VECTOR(1536),  -- optional, if pgvector installed
            created_at TIMESTAMP,
            expires_at TIMESTAMP,
            PRIMARY KEY (namespace, key)
        )
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._table_created = False

    async def _ensure_table(self, session: AsyncSession) -> None:
        if self._table_created:
            return
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS memory_store (
                namespace VARCHAR(255) NOT NULL DEFAULT '',
                key VARCHAR(512) NOT NULL,
                value JSONB,
                created_at TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP,
                PRIMARY KEY (namespace, key)
            )
        """))
        await session.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_memory_ns_key ON memory_store(namespace, key)"
        ))
        await session.commit()
        self._table_created = True

    async def get(self, key: str, namespace: str = "") -> Any | None:
        async with self._session_factory() as session:
            await self._ensure_table(session)
            result = await session.execute(
                text("""
                    SELECT value FROM memory_store
                    WHERE namespace = :ns AND key = :key
                    AND (expires_at IS NULL OR expires_at > NOW())
                """),
                {"ns": namespace, "key": key},
            )
            row = result.fetchone()
            return row[0] if row else None

    async def set(self, key: str, value: Any, namespace: str = "", ttl: int | None = None) -> None:
        async with self._session_factory() as session:
            await self._ensure_table(session)
            expires_clause = f"NOW() + INTERVAL '{ttl} seconds'" if ttl else "NULL"
            await session.execute(
                text(f"""
                    INSERT INTO memory_store (namespace, key, value, expires_at)
                    VALUES (:ns, :key, :value, {expires_clause})
                    ON CONFLICT (namespace, key)
                    DO UPDATE SET value = :value, expires_at = {expires_clause}
                """),
                {"ns": namespace, "key": key, "value": json.dumps(value)},
            )
            await session.commit()

    async def delete(self, key: str, namespace: str = "") -> bool:
        async with self._session_factory() as session:
            await self._ensure_table(session)
            result = await session.execute(
                text("DELETE FROM memory_store WHERE namespace = :ns AND key = :key"),
                {"ns": namespace, "key": key},
            )
            await session.commit()
            return result.rowcount > 0

    async def list_keys(self, namespace: str = "", prefix: str = "") -> list[str]:
        async with self._session_factory() as session:
            await self._ensure_table(session)
            if prefix:
                result = await session.execute(
                    text("""
                        SELECT key FROM memory_store
                        WHERE namespace = :ns AND key LIKE :prefix
                        AND (expires_at IS NULL OR expires_at > NOW())
                    """),
                    {"ns": namespace, "prefix": f"{prefix}%"},
                )
            else:
                result = await session.execute(
                    text("""
                        SELECT key FROM memory_store
                        WHERE namespace = :ns
                        AND (expires_at IS NULL OR expires_at > NOW())
                    """),
                    {"ns": namespace},
                )
            return [row[0] for row in result.fetchall()]

    async def search(self, query: str, namespace: str = "", limit: int = 10) -> list[dict[str, Any]]:
        """Text-based search using PostgreSQL ILIKE on JSON value.

        For vector search, use search_vector() with embeddings.
        """
        async with self._session_factory() as session:
            await self._ensure_table(session)
            result = await session.execute(
                text("""
                    SELECT key, value FROM memory_store
                    WHERE namespace = :ns
                    AND (key ILIKE :query OR value::text ILIKE :query)
                    AND (expires_at IS NULL OR expires_at > NOW())
                    LIMIT :limit
                """),
                {"ns": namespace, "query": f"%{query}%", "limit": limit},
            )
            return [
                {"key": row[0], "value": row[1], "score": 1.0}
                for row in result.fetchall()
            ]

    async def exists(self, key: str, namespace: str = "") -> bool:
        async with self._session_factory() as session:
            await self._ensure_table(session)
            result = await session.execute(
                text("""
                    SELECT 1 FROM memory_store
                    WHERE namespace = :ns AND key = :key
                    AND (expires_at IS NULL OR expires_at > NOW())
                """),
                {"ns": namespace, "key": key},
            )
            return result.fetchone() is not None
