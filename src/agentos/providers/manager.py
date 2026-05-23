"""Multi-provider LLM manager.

Abstracts MAF provider packages behind a unified interface.
Agents specify (provider, model) and the manager resolves to a MAF chat client.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from agentos.config import AgentOSConfig, ProviderItemConfig

logger = logging.getLogger(__name__)


class ChatClientProtocol(Protocol):
    """Protocol matching MAF's SupportsChatGetResponse."""

    async def get_response(self, messages: list[Any], **kwargs: Any) -> Any: ...


@dataclass
class ProviderInfo:
    """Information about a registered provider."""

    name: str
    enabled: bool
    default_model: str
    models: list[str]


class ProviderError(Exception):
    """Raised when a provider operation fails."""


class ProviderManager:
    """Manages multiple LLM provider configurations.

    Resolves (provider_name, model) → MAF ChatClient.
    Providers are registered from config and lazily instantiate clients.

    Usage:
        manager = ProviderManager(config)
        manager.initialize()
        client = manager.get_client("openai", "gpt-4.1")
        agent = client.as_agent(name="MyAgent", instructions="...")
    """

    def __init__(self, config: AgentOSConfig) -> None:
        self._config = config
        self._provider_configs: dict[str, ProviderItemConfig] = {}
        self._client_cache: dict[str, Any] = {}  # (provider:model) -> ChatClient

    def initialize(self) -> None:
        """Register providers from configuration."""
        providers = self._config.providers

        if providers.openai.enabled:
            self._provider_configs["openai"] = providers.openai
            logger.info("Provider registered: openai (default_model=%s)", providers.openai.default_model)

        if providers.anthropic.enabled:
            self._provider_configs["anthropic"] = providers.anthropic
            logger.info("Provider registered: anthropic (default_model=%s)", providers.anthropic.default_model)

        if providers.ollama.enabled:
            self._provider_configs["ollama"] = providers.ollama
            logger.info("Provider registered: ollama (default_model=%s)", providers.ollama.default_model)

        if not self._provider_configs:
            logger.warning("No LLM providers enabled. Agents will not be able to use LLM inference.")

    def get_client(self, provider_name: str | None = None, model: str | None = None) -> Any:
        """Get or create a MAF ChatClient for the given provider and model.

        Args:
            provider_name: Provider name ('openai', 'anthropic', 'ollama'). Defaults to config default.
            model: Model name. Defaults to provider's default model.

        Returns:
            A MAF ChatClient instance.
        """
        provider_name = provider_name or self._config.default_provider
        provider_cfg = self._provider_configs.get(provider_name)
        if provider_cfg is None:
            raise ProviderError(
                f"Provider '{provider_name}' not available. "
                f"Enabled providers: {', '.join(self._provider_configs.keys())}"
            )

        model = model or provider_cfg.default_model
        cache_key = f"{provider_name}:{model}"

        if cache_key in self._client_cache:
            return self._client_cache[cache_key]

        client = self._create_client(provider_name, provider_cfg, model)
        self._client_cache[cache_key] = client
        logger.info("Created %s client for model '%s'", provider_name, model)
        return client

    def _create_client(self, provider_name: str, cfg: ProviderItemConfig, model: str) -> Any:
        """Create a MAF ChatClient for a specific provider.

        Each provider uses its MAF package to create the appropriate client.
        """
        if provider_name == "openai":
            return self._create_openai_client(cfg, model)
        elif provider_name == "anthropic":
            return self._create_anthropic_client(cfg, model)
        elif provider_name == "ollama":
            return self._create_ollama_client(cfg, model)
        else:
            raise ProviderError(f"Unknown provider: {provider_name}")

    def _create_openai_client(self, cfg: ProviderItemConfig, model: str) -> Any:
        """Create an OpenAI ChatClient using MAF's agent-framework-openai."""
        try:
            from agent_framework.openai import OpenAIChatClient

            kwargs: dict[str, Any] = {"model": model}
            if cfg.api_key:
                kwargs["api_key"] = cfg.api_key
            if cfg.api_base:
                kwargs["azure_endpoint"] = cfg.api_base
                kwargs["api_version"] = cfg.api_version or "2024-12-01-preview"

            return OpenAIChatClient(**kwargs)
        except ImportError:
            raise ProviderError(
                "agent-framework-openai not installed. Run: pip install agent-framework-openai"
            )

    def _create_anthropic_client(self, cfg: ProviderItemConfig, model: str) -> Any:
        """Create an Anthropic ChatClient using MAF's agent-framework-anthropic."""
        try:
            from agent_framework.anthropic import AnthropicChatClient

            kwargs: dict[str, Any] = {"model": model}
            if cfg.api_key:
                kwargs["api_key"] = cfg.api_key

            return AnthropicChatClient(**kwargs)
        except ImportError:
            raise ProviderError(
                "agent-framework-anthropic not installed. Run: pip install agent-framework-anthropic"
            )

    def _create_ollama_client(self, cfg: ProviderItemConfig, model: str) -> Any:
        """Create an Ollama ChatClient using MAF's agent-framework-ollama."""
        try:
            from agent_framework.ollama import OllamaChatClient

            kwargs: dict[str, Any] = {"model": model}
            if cfg.base_url:
                kwargs["host"] = cfg.base_url

            return OllamaChatClient(**kwargs)
        except ImportError:
            raise ProviderError(
                "agent-framework-ollama not installed. Run: pip install agent-framework-ollama"
            )

    def list_providers(self) -> list[str]:
        """List enabled provider names."""
        return list(self._provider_configs.keys())

    def get_provider_info(self, provider_name: str) -> ProviderInfo | None:
        """Get info about a provider."""
        cfg = self._provider_configs.get(provider_name)
        if cfg is None:
            return None
        return ProviderInfo(
            name=provider_name,
            enabled=cfg.enabled,
            default_model=cfg.default_model,
            models=[cfg.default_model],  # TODO: query available models from provider
        )

    def get_default_provider(self) -> str:
        """Get the default provider name."""
        return self._config.default_provider
