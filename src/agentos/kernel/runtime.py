"""AgentOS Runtime — bootstraps and orchestrates all subsystems.

The runtime is the central coordinator that initializes the event bus,
registry, lifecycle manager, provider manager, and other subsystems.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agentos.config import AgentOSConfig, load_config
from agentos.kernel.events import EventBus
from agentos.kernel.lifecycle import LifecycleManager
from agentos.kernel.registry import AgentRegistry
from agentos.security.audit import AuditLogger

if TYPE_CHECKING:
    from agentos.agents.factory import AgentFactory
    from agentos.agents.supervisor import SupervisorAgent
    from agentos.communication.bus import MessageBus
    from agentos.db.repositories.agent_repository import AgentRepository
    from agentos.db.repositories.audit_repository import AuditRepository
    from agentos.providers.manager import ProviderManager
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


class AgentOSRuntime:
    """Core AgentOS runtime that manages all subsystems.

    Usage:
        runtime = AgentOSRuntime()
        await runtime.start()
        # ... use runtime.registry, runtime.lifecycle, runtime.providers, etc.
        await runtime.shutdown()
    """

    def __init__(self, config: AgentOSConfig | None = None) -> None:
        self.config = config or load_config()

        # Core subsystems
        self.event_bus = EventBus()
        # Registry/audit are (re)created in start() once DB repos are ready.
        self.registry = AgentRegistry(max_agents=self.config.registry.max_agents)
        self.lifecycle = LifecycleManager(self.registry, self.event_bus)
        self.audit_logger: AuditLogger = AuditLogger()
        self._provider_manager: ProviderManager | None = None
        self._message_bus: MessageBus | None = None
        self._supervisor: SupervisorAgent | None = None
        self._factory: AgentFactory | None = None
        self._db_engine: AsyncEngine | None = None
        self._agent_repo: AgentRepository | None = None
        self._audit_repo: AuditRepository | None = None

        self._started = False

    @property
    def providers(self) -> ProviderManager:
        """Access the provider manager (initialized on start)."""
        if self._provider_manager is None:
            raise RuntimeError("Runtime not started. Call await runtime.start() first.")
        return self._provider_manager

    @property
    def message_bus(self) -> MessageBus:
        """Access the message bus (initialized on start)."""
        if self._message_bus is None:
            raise RuntimeError("Runtime not started. Call await runtime.start() first.")
        return self._message_bus

    @property
    def supervisor(self) -> SupervisorAgent:
        """Access the supervisor agent (initialized on start)."""
        if self._supervisor is None:
            raise RuntimeError("Runtime not started. Call await runtime.start() first.")
        return self._supervisor

    @property
    def factory(self) -> AgentFactory:
        """Access the agent factory (initialized on start)."""
        if self._factory is None:
            raise RuntimeError("Runtime not started. Call await runtime.start() first.")
        return self._factory

    async def _init_database(self) -> bool:
        """Initialize DB engine, repositories, and ensure default tenant exists.

        Returns:
            True if persistence was successfully wired up, False if the database
            is unreachable (runtime falls back to in-memory mode).
        """
        from agentos.db.session import init_engine, get_session_factory
        from agentos.db.repositories.agent_repository import AgentRepository
        from agentos.db.repositories.audit_repository import AuditRepository

        try:
            self._db_engine = init_engine(self.config.database)
            session_factory = get_session_factory()
        except Exception as exc:
            logger.warning(
                "Database not available, running in memory-only mode (%s)",
                exc,
            )
            return False

        # Ensure the default tenant exists so FK constraint won't fire on agent insert.
        try:
            await self._ensure_default_tenant(session_factory)
        except Exception as exc:
            logger.error(
                "Could not ensure default tenant — falling back to memory-only mode: %s",
                exc,
            )
            return False

        self._agent_repo = AgentRepository(session_factory)
        self._audit_repo = AuditRepository(session_factory)

        # Replace the in-memory-only registry with a DB-backed one.
        self.registry = AgentRegistry(
            max_agents=self.config.registry.max_agents,
            repository=self._agent_repo,
        )
        # LifecycleManager held a reference to the old registry; rebind it.
        self.lifecycle = LifecycleManager(self.registry, self.event_bus)
        self.audit_logger = AuditLogger(repository=self._audit_repo)

        # Restore agents from previous runs.
        try:
            await self.registry.restore_from_db()
        except Exception as exc:
            logger.error("DB query failed during restore_from_db: %s", exc)
            # Reset to in-memory mode so the runtime can still start.
            self.registry = AgentRegistry(max_agents=self.config.registry.max_agents)
            self.lifecycle = LifecycleManager(self.registry, self.event_bus)
            self.audit_logger = AuditLogger()
            self._agent_repo = None
            self._audit_repo = None
            return False

        return True

    @staticmethod
    async def _ensure_default_tenant(session_factory) -> None:
        """Insert the 'default' tenant if it does not already exist."""
        from agentos.db.models import TenantModel
        async with session_factory() as session:
            existing = await session.get(TenantModel, "default")
            if existing is None:
                session.add(TenantModel(
                    id="default",
                    name="default",
                    display_name="Default Tenant",
                ))
                await session.commit()
                logger.info("Created default tenant")

    async def start(self) -> None:
        """Start the AgentOS runtime and all subsystems."""
        if self._started:
            logger.warning("Runtime already started")
            return

        logger.info("Starting AgentOS runtime...")

        # Start event bus
        await self.event_bus.start()

        # Initialize database + repositories (best-effort; graceful fallback to memory mode)
        await self._init_database()

        # Initialize provider manager
        from agentos.providers.manager import ProviderManager
        self._provider_manager = ProviderManager(self.config)
        self._provider_manager.initialize()

        # Initialize message bus
        from agentos.communication.bus import MessageBus
        self._message_bus = MessageBus(self.event_bus)
        await self._message_bus.start()

        # Initialize supervisor
        from agentos.agents.supervisor import SupervisorAgent
        self._supervisor = SupervisorAgent(
            self.registry, self.lifecycle, self.event_bus,
        )
        await self._supervisor.start()

        # Initialize agent factory
        from agentos.agents.factory import AgentFactory
        self._factory = AgentFactory(
            registry=self.registry,
            provider_manager=self._provider_manager,
            default_provider=self.config.default_provider,
        )

        self._started = True
        logger.info(
            "AgentOS runtime started (providers: %s, max_agents: %d, persistence: %s)",
            ", ".join(self._provider_manager.list_providers()),
            self.config.registry.max_agents,
            "enabled" if self._agent_repo else "memory-only",
        )

    async def shutdown(self) -> None:
        """Gracefully shut down the runtime and all subsystems."""
        if not self._started:
            return

        logger.info("Shutting down AgentOS runtime...")

        # Stop supervisor
        if self._supervisor:
            await self._supervisor.stop()

        # Stop all running agents
        from agentos.kernel.registry import AgentStatus
        running_agents = self.registry.list_agents(status=AgentStatus.RUNNING)
        for agent_meta in running_agents:
            try:
                await self.lifecycle.stop_agent(agent_meta.agent_id)
            except Exception:
                logger.exception("Error stopping agent '%s'", agent_meta.name)

        # Stop message bus
        if self._message_bus:
            await self._message_bus.stop()

        # Stop event bus
        await self.event_bus.stop()

        # Close DB engine
        if self._db_engine is not None:
            from agentos.db.session import close_engine
            try:
                await close_engine()
            except Exception:
                logger.exception("Error closing DB engine")
            self._db_engine = None

        self._started = False
        logger.info("AgentOS runtime stopped")

    @property
    def is_running(self) -> bool:
        return self._started
