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

# Known model families per provider
_KNOWN_MODELS: dict[str, list[str]] = {
    "openai": [
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "o1",
        "o1-mini",
        "o3-mini",
    ],
    "anthropic": [
        "claude-sonnet-4-6",
        "claude-opus-4-6",
        "claude-haiku-4-5",
        "claude-3-5-sonnet",
        "claude-3-5-haiku",
        "claude-3-opus",
    ],
    "ollama": [
        "llama3.2",
        "llama3.1",
        "llama3",
        "mistral",
        "mixtral",
        "codellama",
        "deepseek-r1",
        "qwen2.5",
    ],
    "deepseek": [
        "deepseek-chat",
        "deepseek-coder",
        "deepseek-reasoner",
    ],
    "qwen": [
        "qwen-turbo",
        "qwen-plus",
        "qwen-max",
        "qwen-max-longcontext",
        "qwen-coder-turbo",
        "qwq-plus",
    ],
    "zhipu": [
        "glm-4-flash",
        "glm-4-plus",
        "glm-4",
        "glm-4-air",
        "glm-4-long",
    ],
    "moonshot": [
        "moonshot-v1-8k",
        "moonshot-v1-32k",
        "moonshot-v1-128k",
    ],
    "doubao": [
        "doubao-1.5-pro-32k",
        "doubao-1.5-pro-256k",
        "doubao-lite-32k",
    ],
}

# Providers that use OpenAI-compatible APIs
_OPENAI_COMPATIBLE = {"deepseek", "qwen", "zhipu", "moonshot", "doubao"}


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
        self._raw_yaml_values: dict[str, dict[str, Any]] = {}  # raw YAML before env-var expansion

    def initialize(self) -> None:
        """Register providers from configuration."""
        import yaml
        from pathlib import Path

        # Load raw YAML values (before env-var expansion) for config persistence
        config_path = Path("configs/agentos.yaml")
        if config_path.exists():
            try:
                with open(config_path) as f:
                    raw = yaml.safe_load(f) or {}
                self._raw_yaml_values = raw.get("providers", {})
            except Exception:
                pass

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

        # Domestic Chinese LLM providers (all OpenAI-compatible)
        for name in ("deepseek", "qwen", "zhipu", "moonshot", "doubao"):
            cfg = getattr(providers, name, None)
            if cfg and cfg.enabled:
                self._provider_configs[name] = cfg
                logger.info("Provider registered: %s (default_model=%s)", name, cfg.default_model)

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
        elif provider_name in _OPENAI_COMPATIBLE:
            return self._create_openai_compatible_client(provider_name, cfg, model)
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

    def _create_openai_compatible_client(
        self, provider_name: str, cfg: ProviderItemConfig, model: str,
    ) -> Any:
        """Create a client for an OpenAI-compatible API (deepseek, qwen, zhipu, etc.).

        Uses ``OpenAICompatChatClient`` which calls the standard Chat Completions
        API (``/v1/chat/completions``).  MAF v1.6 hardcodes ``responses_mode=True``
        which hits ``/v1/responses`` — an endpoint that most domestic LLM providers
        do not support, causing a 404 error.
        """
        from agentos.providers.openai_compat_client import OpenAICompatChatClient

        return OpenAICompatChatClient(
            model=model,
            api_key=cfg.api_key or "",
            base_url=cfg.base_url or "",
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
            models=_KNOWN_MODELS.get(provider_name, [cfg.default_model]),
        )

    def get_default_provider(self) -> str:
        """Get the default provider name."""
        return self._config.default_provider

    def update_provider(
        self,
        provider_name: str,
        enabled: bool | None = None,
        api_key: str | None = None,
        default_model: str | None = None,
        base_url: str | None = None,
        api_base: str | None = None,
    ) -> ProviderInfo:
        """Update a provider's runtime configuration.

        Changes apply immediately to new agent starts.  Existing agents
        are not affected until they are restarted.

        Config is automatically saved to ``configs/agentos.yaml`` so
        that changes persist across server restarts.

        Raises ``ValueError`` if the provider is unknown.
        """
        cfg = self._provider_configs.get(provider_name)
        if cfg is None:
            raise ValueError(
                f"Unknown provider '{provider_name}'. "
                f"Available: {', '.join(self._provider_configs.keys())}"
            )

        if enabled is not None:
            cfg.enabled = enabled
        if api_key is not None:
            cfg.api_key = api_key
        if default_model is not None:
            cfg.default_model = default_model
        if base_url is not None:
            cfg.base_url = base_url
        if api_base is not None:
            cfg.api_base = api_base

        # Invalidate cached clients so they pick up the new config
        keys_to_clear = [
            k for k in self._client_cache if k.startswith(f"{provider_name}:")
        ]
        for k in keys_to_clear:
            del self._client_cache[k]

        # Persist to YAML so config survives restarts
        self._save_provider_config(provider_name, cfg)

        logger.info(
            "Updated provider '%s': enabled=%s, model=%s",
            provider_name, cfg.enabled, cfg.default_model,
        )
        return self.get_provider_info(provider_name)  # type: ignore[return-value]

    def _save_provider_config(
        self, provider_name: str, cfg: ProviderItemConfig,
    ) -> None:
        """Write a provider's runtime config back to ``configs/agentos.yaml``.

        Preserves ``${ENV_VAR}`` references from the original YAML unless
        the user explicitly changed the value via the Admin UI.
        """
        import yaml
        from pathlib import Path

        config_path = Path("configs/agentos.yaml")
        if not config_path.exists():
            logger.warning("Config file not found at %s — skip persist", config_path)
            return

        try:
            # Read the file as text first to preserve env var references
            with open(config_path) as f:
                raw_text = f.read()

            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            logger.exception("Failed to read config for persist")
            return

        providers = data.setdefault("providers", {})
        section = providers.setdefault(provider_name, {})

        # Persist each field, preserving env-var placeholders when possible
        section["enabled"] = cfg.enabled

        # api_key: keep the original ${VAR} reference unless explicitly changed
        raw_prov = self._raw_yaml_values.get(provider_name, {})
        raw_api_key = raw_prov.get("api_key", "")
        if cfg.api_key and raw_api_key and raw_api_key.startswith("${") and not cfg.api_key.startswith("${"):
            # User set an explicit key via UI — write it
            section["api_key"] = cfg.api_key
        elif raw_api_key and raw_api_key.startswith("${"):
            # Keep the original env var reference in YAML
            section["api_key"] = raw_api_key
        else:
            section["api_key"] = cfg.api_key

        if cfg.default_model:
            section["default_model"] = cfg.default_model
        if cfg.base_url:
            section["base_url"] = cfg.base_url
        if cfg.api_base:
            section["api_base"] = cfg.api_base

        try:
            with open(config_path, "w") as f:
                yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            logger.info("Persisted provider '%s' to %s", provider_name, config_path)
        except Exception:
            logger.exception("Failed to write config to %s", config_path)
