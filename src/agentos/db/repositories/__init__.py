"""Data access repositories for AgentOS entities.

Provides CRUD operations over SQLAlchemy async sessions.
Each repository handles one entity type.

This package consolidates session-scoped repositories. The two
session-factory-scoped repositories (``AgentRepository`` and ``AuditRepository``)
live in dedicated modules within this package and may be imported via:

    from agentos.db.repositories.agent_repository import AgentRepository
    from agentos.db.repositories.audit_repository import AuditRepository
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agentos.db.models import (
    AuditLogModel,
    MessageModel,
    SessionModel,
    TenantModel,
    TokenUsageModel,
    WorkflowRunModel,
)

logger = logging.getLogger(__name__)


class TenantRepository:
    """CRUD for tenants."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, tenant_id: str, name: str, display_name: str = "", settings: dict | None = None) -> TenantModel:
        tenant = TenantModel(id=tenant_id, name=name, display_name=display_name, settings=settings or {})
        self._session.add(tenant)
        await self._session.flush()
        return tenant

    async def get(self, tenant_id: str) -> TenantModel | None:
        return await self._session.get(TenantModel, tenant_id)

    async def get_by_name(self, name: str) -> TenantModel | None:
        result = await self._session.execute(select(TenantModel).where(TenantModel.name == name))
        return result.scalar_one_or_none()

    async def list_all(self, active_only: bool = True) -> list[TenantModel]:
        stmt = select(TenantModel)
        if active_only:
            stmt = stmt.where(TenantModel.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_settings(self, tenant_id: str, settings: dict) -> None:
        await self._session.execute(
            update(TenantModel).where(TenantModel.id == tenant_id).values(settings=settings)
        )

    async def deactivate(self, tenant_id: str) -> None:
        await self._session.execute(
            update(TenantModel).where(TenantModel.id == tenant_id).values(is_active=False)
        )


class SessionRepository:
    """CRUD for sessions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **kwargs: Any) -> SessionModel:
        session_model = SessionModel(**kwargs)
        self._session.add(session_model)
        await self._session.flush()
        return session_model

    async def get(self, session_id: str) -> SessionModel | None:
        return await self._session.get(SessionModel, session_id)

    async def list_by_agent(self, agent_id: str) -> list[SessionModel]:
        result = await self._session.execute(
            select(SessionModel).where(SessionModel.agent_id == agent_id)
        )
        return list(result.scalars().all())

    async def append_message(self, session_id: str, message: dict) -> None:
        session = await self.get(session_id)
        if session:
            msgs = list(session.messages)
            msgs.append(message)
            session.messages = msgs


class TokenUsageRepository:
    """CRUD and aggregation for token usage tracking."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, **kwargs: Any) -> TokenUsageModel:
        usage = TokenUsageModel(**kwargs)
        self._session.add(usage)
        await self._session.flush()
        return usage

    async def get_agent_total(self, agent_id: str) -> dict[str, int]:
        result = await self._session.execute(
            select(
                func.sum(TokenUsageModel.input_tokens),
                func.sum(TokenUsageModel.output_tokens),
                func.sum(TokenUsageModel.total_tokens),
                func.sum(TokenUsageModel.cost_usd),
            ).where(TokenUsageModel.agent_id == agent_id)
        )
        row = result.one()
        return {
            "input_tokens": row[0] or 0,
            "output_tokens": row[1] or 0,
            "total_tokens": row[2] or 0,
            "cost_usd": float(row[3] or 0),
        }

    async def get_tenant_total(self, tenant_id: str, since: datetime | None = None) -> dict[str, Any]:
        stmt = select(
            func.sum(TokenUsageModel.input_tokens),
            func.sum(TokenUsageModel.output_tokens),
            func.sum(TokenUsageModel.total_tokens),
            func.sum(TokenUsageModel.cost_usd),
            func.count(),
        ).where(TokenUsageModel.tenant_id == tenant_id)
        if since:
            stmt = stmt.where(TokenUsageModel.timestamp >= since)
        result = await self._session.execute(stmt)
        row = result.one()
        return {
            "input_tokens": row[0] or 0,
            "output_tokens": row[1] or 0,
            "total_tokens": row[2] or 0,
            "cost_usd": float(row[3] or 0),
            "request_count": row[4] or 0,
        }


class AuditLogRepository:
    """CRUD for audit logs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log(self, **kwargs: Any) -> AuditLogModel:
        entry = AuditLogModel(**kwargs)
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def query(
        self,
        tenant_id: str | None = None,
        agent_id: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[AuditLogModel]:
        stmt = select(AuditLogModel).order_by(AuditLogModel.timestamp.desc()).limit(limit)
        if tenant_id:
            stmt = stmt.where(AuditLogModel.tenant_id == tenant_id)
        if agent_id:
            stmt = stmt.where(AuditLogModel.agent_id == agent_id)
        if action:
            stmt = stmt.where(AuditLogModel.action == action)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class WorkflowRunRepository:
    """CRUD for workflow runs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **kwargs: Any) -> WorkflowRunModel:
        run = WorkflowRunModel(**kwargs)
        self._session.add(run)
        await self._session.flush()
        return run

    async def get(self, run_id: str) -> WorkflowRunModel | None:
        return await self._session.get(WorkflowRunModel, run_id)

    async def update_status(self, run_id: str, status: str, **kwargs: Any) -> None:
        values = {"status": status, **kwargs}
        await self._session.execute(
            update(WorkflowRunModel).where(WorkflowRunModel.id == run_id).values(**values)
        )

    async def list_by_tenant(self, tenant_id: str, status: str | None = None, limit: int = 50) -> list[WorkflowRunModel]:
        stmt = select(WorkflowRunModel).where(
            WorkflowRunModel.tenant_id == tenant_id
        ).order_by(WorkflowRunModel.created_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(WorkflowRunModel.status == status)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class MessageRepository:
    """CRUD for persisted messages."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, **kwargs: Any) -> MessageModel:
        msg = MessageModel(**kwargs)
        self._session.add(msg)
        await self._session.flush()
        return msg

    async def get_conversation(self, correlation_id: str) -> list[MessageModel]:
        result = await self._session.execute(
            select(MessageModel).where(
                MessageModel.correlation_id == correlation_id
            ).order_by(MessageModel.timestamp)
        )
        return list(result.scalars().all())


__all__ = [
    "TenantRepository",
    "SessionRepository",
    "TokenUsageRepository",
    "AuditLogRepository",
    "WorkflowRunRepository",
    "MessageRepository",
]
