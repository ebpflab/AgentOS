"""Agent Registry — capability-based agent discovery and management.

Central registry where agents register their capabilities and metadata.
Other agents and the system discover agents by querying capabilities.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agentos.db.repositories.agent_repository import AgentRepository

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Agent lifecycle states."""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class AgentMetadata:
    """Metadata associated with a registered agent."""

    agent_id: str
    name: str
    description: str = ""
    instructions: str = ""
    capabilities: list[str] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    tenant_id: str = "default"
    status: AgentStatus = AgentStatus.CREATED
    tags: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


class AgentRegistryError(Exception):
    """Raised for registry-related errors."""


class AgentRegistry:
    """In-memory agent registry with capability-based discovery.

    Optionally backed by a persistent repository: when ``repository`` is
    provided, register/unregister/update_status are also persisted to DB.
    Persistence is fire-and-forget — DB failures are logged but never
    propagate to callers so the in-process registry remains authoritative.

    Usage:
        registry = AgentRegistry(max_agents=100, repository=repo)
        registry.register(metadata, agent_instance)
        agents = registry.find_by_capability("code-review")
        registry.unregister("agent-id")
    """

    def __init__(
        self,
        max_agents: int = 100,
        repository: AgentRepository | None = None,
    ) -> None:
        self._max_agents = max_agents
        self._agents: dict[str, AgentMetadata] = {}
        self._instances: dict[str, Any] = {}  # agent_id -> MAF Agent instance
        self._sessions: dict[str, Any] = {}   # session_id -> MAF AgentSession
        self._repository = repository

    def register(self, metadata: AgentMetadata, instance: Any = None) -> None:
        """Register an agent with its metadata.

        Args:
            metadata: Agent metadata including capabilities.
            instance: The MAF Agent instance (optional, can be set later).

        Raises:
            AgentRegistryError: If max agents exceeded or duplicate ID.
        """
        if metadata.agent_id in self._agents:
            raise AgentRegistryError(f"Agent already registered: {metadata.agent_id}")
        if len(self._agents) >= self._max_agents:
            raise AgentRegistryError(
                f"Maximum agents ({self._max_agents}) reached. Cannot register '{metadata.name}'."
            )

        self._agents[metadata.agent_id] = metadata
        if instance is not None:
            self._instances[metadata.agent_id] = instance
        logger.info("Registered agent '%s' (id=%s)", metadata.name, metadata.agent_id[:8])

        self._persist_async(self._repository.add(metadata) if self._repository else None)

    def unregister(self, agent_id: str) -> AgentMetadata | None:
        """Remove an agent from the registry.

        Returns:
            The removed metadata, or None if not found.
        """
        metadata = self._agents.pop(agent_id, None)
        self._instances.pop(agent_id, None)
        if metadata:
            logger.info("Unregistered agent '%s' (id=%s)", metadata.name, agent_id[:8])
            self._persist_async(self._repository.remove(agent_id) if self._repository else None)
        return metadata

    def get(self, agent_id: str) -> AgentMetadata | None:
        """Get agent metadata by ID."""
        return self._agents.get(agent_id)

    def get_instance(self, agent_id: str) -> Any | None:
        """Get the MAF Agent instance by ID."""
        return self._instances.get(agent_id)

    def set_instance(self, agent_id: str, instance: Any) -> None:
        """Associate a MAF Agent instance with a registered agent."""
        if agent_id not in self._agents:
            raise AgentRegistryError(f"Agent not registered: {agent_id}")
        self._instances[agent_id] = instance

    def update_status(self, agent_id: str, status: AgentStatus) -> None:
        """Update an agent's status (in-memory + persisted)."""
        metadata = self._agents.get(agent_id)
        if metadata:
            metadata.status = status
            logger.debug("Agent %s status → %s", agent_id[:8], status.value)
            self._persist_async(
                self._repository.update_status(agent_id, status.value) if self._repository else None
            )

    def find_by_capability(self, capability: str, tenant_id: str | None = None) -> list[AgentMetadata]:
        """Find agents that have a specific capability.

        Args:
            capability: The capability to search for.
            tenant_id: Optional tenant filter.

        Returns:
            List of matching agent metadata.
        """
        results = []
        for meta in self._agents.values():
            if capability in meta.capabilities:
                if tenant_id is None or meta.tenant_id == tenant_id:
                    results.append(meta)
        return results

    def find_by_name(self, name: str, tenant_id: str | None = None) -> AgentMetadata | None:
        """Find an agent by name."""
        for meta in self._agents.values():
            if meta.name == name:
                if tenant_id is None or meta.tenant_id == tenant_id:
                    return meta
        return None

    def list_agents(self, tenant_id: str | None = None, status: AgentStatus | None = None) -> list[AgentMetadata]:
        """List all registered agents, optionally filtered.

        Args:
            tenant_id: Filter by tenant.
            status: Filter by status.
        """
        results = []
        for meta in self._agents.values():
            if tenant_id and meta.tenant_id != tenant_id:
                continue
            if status and meta.status != status:
                continue
            results.append(meta)
        return results

    async def restore_from_db(self) -> int:
        """Re-populate the in-memory registry from the persistent store.

        Called once at startup to reload agents persisted in previous runs.

        Returns:
            Number of agents restored (0 if no repository configured or DB empty).

        Raises:
            The underlying SQLAlchemy/DBAPI exception if the database is
            unreachable or the query fails. Callers (typically
            ``AgentOSRuntime.start()``) decide whether to abort startup.
        """
        if self._repository is None:
            return 0
        try:
            agents = await self._repository.list_all()
        except Exception as exc:
            logger.error("Failed to restore agents from DB: %s", exc)
            raise
        restored = 0
        for meta in agents:
            if meta.agent_id not in self._agents:
                self._agents[meta.agent_id] = meta
                restored += 1
        if restored:
            logger.info("Restored %d agents from DB (%d already in memory)", restored, len(agents) - restored)
        return restored

    @property
    def repository(self) -> AgentRepository | None:
        return self._repository

    @property
    def count(self) -> int:
        return len(self._agents)

    @property
    def max_agents(self) -> int:
        return self._max_agents

    @staticmethod
    def _persist_async(coro: Any) -> None:
        """Schedule a coroutine as a fire-and-forget background task.

        DB errors are swallowed so they never affect the synchronous caller.
        """
        if coro is None:
            return
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(coro)
            task.add_done_callback(AgentRegistry._log_persist_error)
        except RuntimeError:
            # No running event loop — close the coroutine to avoid
            # "RuntimeWarning: coroutine was never awaited".
            coro.close()

    @staticmethod
    def _log_persist_error(task: asyncio.Task) -> None:  # type: ignore[type-arg]
        exc = task.exception()
        if exc:
            logger.warning("DB persistence error (non-fatal): %s", exc)
