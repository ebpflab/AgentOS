"""ManagedAgent — AgentOS-enhanced wrapper around MAF Agent.

Extends the MAF Agent with lifecycle management, metadata, and
integration with the AgentOS kernel (registry, events, providers).
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from agentos.kernel.registry import AgentMetadata, AgentStatus

logger = logging.getLogger(__name__)


class ManagedAgent:
    """An agent managed by the AgentOS runtime.

    Wraps a MAF Agent instance with:
    - Unique agent_id and metadata
    - Lifecycle status tracking
    - Provider/model configuration
    - Capability registration

    Usage:
        agent = ManagedAgent(
            name="CodeReviewer",
            instructions="You are a code review expert.",
            provider="openai",
            model="gpt-4.1",
            capabilities=["code-review", "python"],
        )
        # The MAF agent instance is created by the factory
        agent.set_maf_agent(maf_agent_instance)
        result = await agent.run("Review this code: ...")
    """

    def __init__(
        self,
        name: str,
        instructions: str = "",
        provider: str = "",
        model: str = "",
        capabilities: list[str] | None = None,
        tenant_id: str = "default",
        agent_id: str | None = None,
        tags: dict[str, str] | None = None,
        tools: list[Any] | None = None,
    ) -> None:
        self.agent_id = agent_id or str(uuid4())
        self.name = name
        self.instructions = instructions
        self.provider = provider
        self.model = model
        self.capabilities = capabilities or []
        self.tenant_id = tenant_id
        self.tags = tags or {}
        self.tools = tools or []
        self._maf_agent: Any = None
        self._session: Any = None

    @property
    def metadata(self) -> AgentMetadata:
        """Build registry metadata for this agent."""
        return AgentMetadata(
            agent_id=self.agent_id,
            name=self.name,
            description=self.instructions[:200] if self.instructions else "",
            instructions=self.instructions,
            capabilities=self.capabilities,
            provider=self.provider,
            model=self.model,
            tenant_id=self.tenant_id,
            tags=self.tags,
        )

    @property
    def maf_agent(self) -> Any:
        """The underlying MAF Agent instance."""
        if self._maf_agent is None:
            raise RuntimeError(f"Agent '{self.name}' has no MAF agent instance. Use factory to create.")
        return self._maf_agent

    def set_maf_agent(self, agent: Any) -> None:
        """Set the underlying MAF Agent instance."""
        self._maf_agent = agent

    @property
    def has_maf_agent(self) -> bool:
        return self._maf_agent is not None

    async def run(self, message: str, session: Any | None = None) -> str:
        """Run the agent with a message.

        Args:
            message: User message to process.
            session: Optional MAF AgentSession for multi-turn conversations.

        Returns:
            Agent's response as string.
        """
        agent = self.maf_agent
        use_session = session or self._session

        if use_session:
            result = await agent.run(message, use_session)
        else:
            result = await agent.run(message)

        return str(result)

    async def create_session(self) -> Any:
        """Create a new MAF AgentSession for multi-turn conversations."""
        agent = self.maf_agent
        self._session = await agent.create_session()
        return self._session

    def as_tool(self) -> Any:
        """Expose this agent as a tool for other agents (MAF .as_tool())."""
        return self.maf_agent.as_tool(
            name=self.name,
            description=self.instructions[:200] if self.instructions else f"Agent: {self.name}",
        )

    def __repr__(self) -> str:
        return (
            f"ManagedAgent(name={self.name!r}, id={self.agent_id[:8]}, "
            f"provider={self.provider!r}, model={self.model!r}, "
            f"capabilities={self.capabilities})"
        )
