"""AuditRepository — persistent CRUD for audit log entries."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentos.db.models import AuditLogModel

logger = logging.getLogger(__name__)


class AuditRepository:
    """Persists AuditEntry objects to the audit_log table."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add(self, entry_data: dict[str, Any]) -> None:
        """Persist a single audit entry dict to the DB.

        Raises:
            ValueError: If ``action`` is missing or empty.
        """
        action = entry_data.get("action")
        if not action:
            raise ValueError("AuditRepository.add() requires a non-empty 'action' field")

        # Use app-level timestamp from the entry; fall back to now if absent
        raw_ts = entry_data.get("timestamp")
        if isinstance(raw_ts, float):
            timestamp = datetime.fromtimestamp(raw_ts, tz=timezone.utc).replace(tzinfo=None)
        elif isinstance(raw_ts, datetime):
            timestamp = raw_ts.replace(tzinfo=None) if raw_ts.tzinfo else raw_ts
        else:
            timestamp = datetime.now(tz=timezone.utc).replace(tzinfo=None)

        async with self._session_factory() as session:
            model = AuditLogModel(
                tenant_id=entry_data.get("tenant_id", "default"),
                agent_id=entry_data.get("agent_id", ""),
                user_id=entry_data.get("user_id", ""),
                action=action,
                resource_type=entry_data.get("resource_type", ""),
                resource_id=entry_data.get("resource_id", ""),
                details=entry_data.get("details", {}),
                outcome=entry_data.get("outcome", "success"),
                timestamp=timestamp,
            )
            session.add(model)
            await session.commit()

    async def query(
        self,
        tenant_id: str | None = None,
        action: str | None = None,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query audit log entries with optional filters."""
        async with self._session_factory() as session:
            stmt = select(AuditLogModel).order_by(AuditLogModel.timestamp.desc())
            if tenant_id:
                stmt = stmt.where(AuditLogModel.tenant_id == tenant_id)
            if action:
                stmt = stmt.where(AuditLogModel.action == action)
            if user_id:
                stmt = stmt.where(AuditLogModel.user_id == user_id)
            stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            return [
                {
                    "id": m.id,
                    "tenant_id": m.tenant_id,
                    "agent_id": m.agent_id,
                    "user_id": m.user_id,
                    "action": m.action,
                    "resource_type": m.resource_type,
                    "resource_id": m.resource_id,
                    "details": m.details,
                    "outcome": m.outcome,
                    "timestamp": m.timestamp,
                }
                for m in result.scalars().all()
            ]

