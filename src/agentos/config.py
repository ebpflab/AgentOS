"""AgentOS configuration loading.

Loads configuration from agentos.yaml with environment variable overrides.
Environment variables use the pattern AGENTOS_<SECTION>_<KEY> (uppercase).
Values in YAML containing ${VAR} are expanded from the environment.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)(?::([^}]*))?\}")


def _expand_env_vars(value: Any) -> Any:
    """Recursively expand ${VAR} and ${VAR:default} in string values."""
    if isinstance(value, str):
        def _replacer(match: re.Match) -> str:
            var_name = match.group(1)
            default = match.group(2)
            return os.environ.get(var_name, default if default is not None else match.group(0))
        return _ENV_VAR_PATTERN.sub(_replacer, value)
    if isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False


class ProviderItemConfig(BaseModel):
    enabled: bool = True
    api_key: str = ""
    default_model: str = ""
    base_url: str = ""
    api_base: str = ""
    api_version: str = ""


class ProvidersConfig(BaseModel):
    openai: ProviderItemConfig = Field(default_factory=ProviderItemConfig)
    anthropic: ProviderItemConfig = Field(default_factory=ProviderItemConfig)
    ollama: ProviderItemConfig = Field(default_factory=lambda: ProviderItemConfig(
        enabled=False, base_url="http://localhost:11434", default_model="llama3.2"
    ))
    # Domestic Chinese LLM providers (all OpenAI-compatible)
    deepseek: ProviderItemConfig = Field(default_factory=lambda: ProviderItemConfig(
        enabled=False, base_url="https://api.deepseek.com/v1", default_model="deepseek-chat",
    ))
    qwen: ProviderItemConfig = Field(default_factory=lambda: ProviderItemConfig(
        enabled=False, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen-plus",
    ))
    zhipu: ProviderItemConfig = Field(default_factory=lambda: ProviderItemConfig(
        enabled=False, base_url="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-4-flash",
    ))
    moonshot: ProviderItemConfig = Field(default_factory=lambda: ProviderItemConfig(
        enabled=False, base_url="https://api.moonshot.cn/v1", default_model="moonshot-v1-8k",
    ))
    doubao: ProviderItemConfig = Field(default_factory=lambda: ProviderItemConfig(
        enabled=False, base_url="https://ark.cn-beijing.volces.com/api/v3",
        default_model="doubao-1.5-pro-32k",
    ))


class DatabaseConfig(BaseModel):
    url: str = "postgresql+asyncpg://agentos:agentos@localhost:5432/agentos"
    pool_size: int = 20
    max_overflow: int = 10


class RegistryConfig(BaseModel):
    max_agents: int = 100


class ModelPricing(BaseModel):
    input_per_1k: float = 0.0
    output_per_1k: float = 0.0


class ResourcesConfig(BaseModel):
    default_token_budget: int = 0
    default_rate_limit: int = 60
    pricing: dict[str, dict[str, ModelPricing]] = Field(default_factory=dict)


class OidcConfig(BaseModel):
    issuer_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    audience: str = ""


class SecurityConfig(BaseModel):
    auth_enabled: bool = False
    oidc: OidcConfig = Field(default_factory=OidcConfig)
    default_tenant: str = "default"


class ObservabilityConfig(BaseModel):
    otlp_endpoint: str = ""
    metrics_enabled: bool = True
    log_level: str = "INFO"
    log_format: str = "json"


class AgentOSConfig(BaseSettings):
    """Root configuration for AgentOS."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    default_provider: str = "openai"
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    registry: RegistryConfig = Field(default_factory=RegistryConfig)
    resources: ResourcesConfig = Field(default_factory=ResourcesConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    agents_dir: str = "configs/agents"
    workflows_dir: str = "configs/workflows"

    model_config = {"env_prefix": "AGENTOS_"}


def load_config(config_path: str | Path | None = None) -> AgentOSConfig:
    """Load AgentOS configuration from YAML file with env var expansion.

    Args:
        config_path: Path to agentos.yaml. If None, searches in default locations.

    Returns:
        Parsed and validated AgentOSConfig.
    """
    search_paths = [
        Path(config_path) if config_path else None,
        Path("configs/agentos.yaml"),
        Path("agentos.yaml"),
        Path.home() / ".agentos" / "agentos.yaml",
    ]

    raw_data: dict[str, Any] = {}
    for path in search_paths:
        if path and path.exists():
            with open(path) as f:
                raw_data = yaml.safe_load(f) or {}
            break

    expanded = _expand_env_vars(raw_data)
    return AgentOSConfig(**expanded)
