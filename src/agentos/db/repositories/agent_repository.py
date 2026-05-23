"""AgentRepository — persistent CRUD for agents.

Uses SQLAlchemy async session to read/write AgentModel.
Maps between AgentModel (DB) and AgentMetadata (kernel) representations.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentos.db.models import AgentModel
from agentos.kernel.registry import AgentMetadata, AgentStatus

logger = logging.getLogger(__name__)


class AgentRepository:
    """Persistent agent storage backed by SQLAlchemy.

    Usage:
        repo = AgentRepository(session_factory)
        await repo.add(metadata)
        agent = await repo.get("agent-id")
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add(self, agent: AgentMetadata) -> None:
        """Upsert an agent — safe to call even if the agent was already persisted."""
        async with self._session_factory() as session:
            model = AgentModel(
                id=agent.agent_id,
                name=agent.name,
                description=agent.description,
                instructions="",
                provider=agent.provider,
                model=agent.model,
                capabilities=agent.capabilities,
                status=agent.status.value if isinstance(agent.status, AgentStatus) else agent.status,
                tenant_id=agent.tenant_id,
                tags=agent.tags,
                agent_metadata=agent.extra,
            )
            # merge() does INSERT or UPDATE — safe on duplicate PK
            await session.merge(model)
            await session.commit()
            logger.debug("Upserted agent '%s' (id=%s)", agent.name, agent.agent_id[:8])

    async def get(self, agent_id: str) -> AgentMetadata | None:
        """Load an agent from the database."""
        async with self._session_factory() as session:
            model = await session.get(AgentModel, agent_id)
            if model is None:
                return None
            # Convert inside the session to avoid DetachedInstanceError
            return self._to_metadata(model)

    async def remove(self, agent_id: str) -> bool:
        """Remove an agent from the database. Returns True if existed."""
        async with self._session_factory() as session:
            result = await session.execute(
                delete(AgentModel).where(AgentModel.id == agent_id)
            )
            await session.commit()
            return (result.rowcount or 0) > 0

    async def list_all(self) -> list[AgentMetadata]:
        """Load all agents from the database."""
        async with self._session_factory() as session:
            result = await session.execute(select(AgentModel))
            # Convert inside the session to avoid DetachedInstanceError
            return [self._to_metadata(m) for m in result.scalars().all()]

    async def find_by_capability(self, capability: str) -> list[AgentMetadata]:
        """Find agents that have a specific capability.

        Loads all agents and filters in Python — works across PostgreSQL and SQLite.
        """
        async with self._session_factory() as session:
            result = await session.execute(select(AgentModel))
            return [
                self._to_metadata(m)
                for m in result.scalars().all()
                if capability in (m.capabilities or [])
            ]

    async def find_by_tenant(self, tenant_id: str) -> list[AgentMetadata]:
        """Find all agents for a given tenant."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(AgentModel).where(AgentModel.tenant_id == tenant_id)
            )
            return [self._to_metadata(m) for m in result.scalars().all()]

    async def update_status(self, agent_id: str, status: str) -> None:
        """Update an agent's status in the database."""
        async with self._session_factory() as session:
            result = await session.execute(
                update(AgentModel)
                .where(AgentModel.id == agent_id)
                .values(status=status)
            )
            await session.commit()
            if (result.rowcount or 0) == 0:
                logger.debug("update_status: agent %s not found in DB", agent_id[:8])

    @staticmethod
    def _to_metadata(model: AgentModel) -> AgentMetadata:
        """Convert a DB model to AgentMetadata.

        Must be called while the model is still attached to a live session.
        """
        try:
            status = AgentStatus(model.status)
        except ValueError:
            status = AgentStatus.CREATED
        return AgentMetadata(
            agent_id=model.id,
            name=model.name,
            description=model.description,
            capabilities=model.capabilities or [],
            provider=model.provider,
            model=model.model,
            tenant_id=model.tenant_id,
            status=status,
            tags=model.tags or {},
            extra=model.agent_metadata or {},
        )
