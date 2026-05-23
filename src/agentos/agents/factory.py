"""Agent Factory — creates ManagedAgents from code configs or YAML.

Handles agent creation, MAF client resolution, and auto-registration
with the kernel registry.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from agentos.agents.base import ManagedAgent
from agentos.kernel.registry import AgentRegistry

if TYPE_CHECKING:
    from agentos.providers.manager import ProviderManager

logger = logging.getLogger(__name__)


class AgentFactory:
    """Creates ManagedAgent instances and registers them.

    Usage:
        factory = AgentFactory(registry, provider_manager)
        agent = await factory.create(
            name="Coder",
            instructions="You are a Python expert.",
            provider="openai",
            model="gpt-4.1",
            capabilities=["coding", "python"],
        )
    """

    def __init__(
        self,
        registry: AgentRegistry,
        provider_manager: ProviderManager,
        default_provider: str = "openai",
    ) -> None:
        self._registry = registry
        self._providers = provider_manager
        self._default_provider = default_provider

    async def create(
        self,
        name: str,
        instructions: str = "You are a helpful assistant.",
        provider: str | None = None,
        model: str | None = None,
        capabilities: list[str] | None = None,
        tenant_id: str = "default",
        tools: list[Any] | None = None,
        tags: dict[str, str] | None = None,
        auto_start: bool = False,
    ) -> ManagedAgent:
        """Create a new ManagedAgent and register it.

        Args:
            name: Agent name.
            instructions: System instructions for the agent.
            provider: LLM provider ('openai', 'anthropic', 'ollama').
            model: Model name (e.g., 'gpt-4.1', 'claude-sonnet-4-6').
            capabilities: List of capabilities for discovery.
            tenant_id: Tenant this agent belongs to.
            tools: Optional list of tools for the agent.
            tags: Optional key-value tags.
            auto_start: If True, immediately start the agent.

        Returns:
            The created ManagedAgent.
        """
        provider = provider or self._default_provider

        # Create the ManagedAgent wrapper
        agent = ManagedAgent(
            name=name,
            instructions=instructions,
            provider=provider,
            model=model or "",
            capabilities=capabilities or [],
            tenant_id=tenant_id,
            tools=tools,
            tags=tags or {},
        )

        # Get the MAF ChatClient from provider manager
        client = self._providers.get_client(provider, model)

        # Create the MAF Agent instance
        maf_agent = client.as_agent(
            name=name,
            instructions=instructions,
        )

        # If tools are provided, add them to the MAF agent
        if tools:
            for tool in tools:
                maf_agent.add_tool(tool)

        agent.set_maf_agent(maf_agent)

        # Register in the kernel registry
        self._registry.register(agent.metadata, maf_agent)

        logger.info(
            "Created agent '%s' (provider=%s, model=%s, capabilities=%s)",
            name, provider, model, capabilities,
        )

        return agent

    async def create_from_yaml(self, yaml_path: str | Path) -> ManagedAgent:
        """Create a ManagedAgent from a YAML definition file.

        Expected YAML format:
            name: "MyAgent"
            instructions: "You are a helpful assistant."
            provider: "openai"
            model: "gpt-4.1"
            capabilities:
              - "summarization"
              - "writing"
            tenant_id: "default"
            tags:
              team: "research"
        """
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"Agent YAML not found: {path}")

        with open(path) as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            raise ValueError(f"Invalid agent YAML: {path}")

        return await self.create(
            name=config["name"],
            instructions=config.get("instructions", "You are a helpful assistant."),
            provider=config.get("provider"),
            model=config.get("model"),
            capabilities=config.get("capabilities", []),
            tenant_id=config.get("tenant_id", "default"),
            tags=config.get("tags", {}),
        )

    async def create_from_directory(self, directory: str | Path) -> list[ManagedAgent]:
        """Load all agent YAML definitions from a directory.

        Returns:
            List of created ManagedAgents.
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            logger.warning("Agents directory not found: %s", dir_path)
            return []

        agents = []
        for yaml_file in sorted(dir_path.glob("*.yaml")):
            try:
                agent = await self.create_from_yaml(yaml_file)
                agents.append(agent)
                logger.info("Loaded agent from %s", yaml_file.name)
            except Exception:
                logger.exception("Failed to load agent from %s", yaml_file)

        return agents
