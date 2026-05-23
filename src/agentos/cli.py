"""AgentOS CLI — command-line interface for managing the Agent OS.

Usage:
    agentos start              Start the AgentOS runtime
    agentos agents list        List registered agents
    agentos agents create      Create a new agent
    agentos agents stop        Stop a running agent
    agentos providers list     List enabled LLM providers
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

import click

try:
    import structlog
    _HAS_STRUCTLOG = True
except ImportError:
    _HAS_STRUCTLOG = False


def _setup_logging(log_level: str = "INFO", log_format: str = "text") -> None:
    """Configure structured logging (uses structlog if available, falls back to stdlib)."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    if _HAS_STRUCTLOG:
        if log_format == "json":
            structlog.configure(
                processors=[
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.add_log_level,
                    structlog.processors.JSONRenderer(),
                ],
                wrapper_class=structlog.make_filtering_bound_logger(level),
            )
        else:
            structlog.configure(
                processors=[
                    structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
                    structlog.processors.add_log_level,
                    structlog.dev.ConsoleRenderer(),
                ],
                wrapper_class=structlog.make_filtering_bound_logger(level),
            )

    logging.basicConfig(level=level, format="%(message)s", stream=sys.stderr)


@click.group()
@click.option("--config", "-c", default=None, help="Path to agentos.yaml config file")
@click.option("--log-level", default="INFO", help="Log level (DEBUG, INFO, WARNING, ERROR)")
@click.pass_context
def cli(ctx: click.Context, config: str | None, log_level: str) -> None:
    """AgentOS — Enterprise Agent Operating System."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["log_level"] = log_level


@cli.command()
@click.option("--host", default=None, help="Server host (overrides config)")
@click.option("--port", default=None, type=int, help="Server port (overrides config)")
@click.pass_context
def start(ctx: click.Context, host: str | None, port: int | None) -> None:
    """Start the AgentOS runtime and API server."""
    _setup_logging(ctx.obj["log_level"])

    from agentos.config import load_config
    from agentos.kernel.runtime import AgentOSRuntime

    config = load_config(ctx.obj["config_path"])
    if host:
        config.server.host = host
    if port:
        config.server.port = port

    runtime = AgentOSRuntime(config)

    click.echo(f"Starting AgentOS on {config.server.host}:{config.server.port}")
    click.echo(f"API docs: http://{config.server.host}:{config.server.port}/docs")

    try:
        import uvicorn
        from agentos.api.server import create_app

        app = create_app()
        uvicorn.run(
            app,
            host=config.server.host,
            port=config.server.port,
            log_level=ctx.obj["log_level"].lower(),
        )
    except ImportError:
        click.echo("uvicorn not installed — running in headless mode (no HTTP API)")
        async def _run() -> None:
            await runtime.start()
            click.echo(f"Providers: {', '.join(runtime.providers.list_providers())}")
            click.echo("Press Ctrl+C to stop.")
            try:
                while runtime.is_running:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass
            finally:
                await runtime.shutdown()
                click.echo("AgentOS stopped.")

        try:
            asyncio.run(_run())
        except KeyboardInterrupt:
            click.echo("\nShutting down...")


# --- Agent subcommands ---

@cli.group()
def agents() -> None:
    """Manage agents."""


@agents.command("list")
@click.option("--tenant", default=None, help="Filter by tenant ID")
@click.option("--status", default=None, help="Filter by status")
@click.option("--format", "fmt", default="table", type=click.Choice(["table", "json"]))
@click.pass_context
def agents_list(ctx: click.Context, tenant: str | None, status: str | None, fmt: str) -> None:
    """List registered agents."""
    from agentos.config import load_config
    from agentos.kernel.registry import AgentRegistry, AgentStatus

    config = load_config(ctx.obj["config_path"])
    registry = AgentRegistry(max_agents=config.registry.max_agents)

    # In a full implementation, this would connect to the running runtime
    # For now, show an empty list with instructions
    status_filter = AgentStatus(status) if status else None
    agents_list_data = registry.list_agents(tenant_id=tenant, status=status_filter)

    if fmt == "json":
        data = [
            {
                "agent_id": a.agent_id,
                "name": a.name,
                "status": a.status.value,
                "provider": a.provider,
                "model": a.model,
                "capabilities": a.capabilities,
                "tenant_id": a.tenant_id,
            }
            for a in agents_list_data
        ]
        click.echo(json.dumps(data, indent=2))
    else:
        if not agents_list_data:
            click.echo("No agents registered. Use 'agentos agents create' to create one.")
            return

        # Simple table output
        click.echo(f"{'NAME':<20} {'STATUS':<12} {'PROVIDER':<12} {'MODEL':<20} {'CAPABILITIES'}")
        click.echo("-" * 80)
        for a in agents_list_data:
            caps = ", ".join(a.capabilities[:3])
            click.echo(f"{a.name:<20} {a.status.value:<12} {a.provider:<12} {a.model:<20} {caps}")


@agents.command("create")
@click.option("--name", "-n", required=True, help="Agent name")
@click.option("--instructions", "-i", default="You are a helpful assistant.", help="System instructions")
@click.option("--provider", "-p", default=None, help="LLM provider (openai, anthropic, ollama)")
@click.option("--model", "-m", default=None, help="Model name")
@click.option("--capabilities", "-c", default="", help="Comma-separated capabilities")
@click.option("--tenant", default="default", help="Tenant ID")
@click.pass_context
def agents_create(
    ctx: click.Context,
    name: str,
    instructions: str,
    provider: str | None,
    model: str | None,
    capabilities: str,
    tenant: str,
) -> None:
    """Create a new agent."""
    _setup_logging(ctx.obj["log_level"])

    from agentos.agents.factory import AgentFactory
    from agentos.config import load_config
    from agentos.kernel.runtime import AgentOSRuntime

    config = load_config(ctx.obj["config_path"])
    caps = [c.strip() for c in capabilities.split(",") if c.strip()]

    async def _create() -> None:
        runtime = AgentOSRuntime(config)
        await runtime.start()

        factory = AgentFactory(
            registry=runtime.registry,
            provider_manager=runtime.providers,
            default_provider=config.default_provider,
        )

        try:
            agent = await factory.create(
                name=name,
                instructions=instructions,
                provider=provider,
                model=model,
                capabilities=caps,
                tenant_id=tenant,
            )
            click.echo(f"Agent created: {agent.name} (id={agent.agent_id[:8]}...)")
            click.echo(f"  Provider: {agent.provider}")
            click.echo(f"  Model: {agent.model}")
            click.echo(f"  Capabilities: {agent.capabilities}")
        except Exception as e:
            click.echo(f"Error creating agent: {e}", err=True)
            raise SystemExit(1)
        finally:
            await runtime.shutdown()

    asyncio.run(_create())


# --- Provider subcommands ---

@cli.group()
def providers() -> None:
    """Manage LLM providers."""


@providers.command("list")
@click.pass_context
def providers_list(ctx: click.Context) -> None:
    """List enabled LLM providers."""
    from agentos.config import load_config
    from agentos.providers.manager import ProviderManager

    config = load_config(ctx.obj["config_path"])
    manager = ProviderManager(config)
    manager.initialize()

    default = config.default_provider
    click.echo(f"{'PROVIDER':<15} {'DEFAULT MODEL':<25} {'DEFAULT'}")
    click.echo("-" * 50)
    for name in manager.list_providers():
        info = manager.get_provider_info(name)
        if info:
            is_default = "  *" if name == default else ""
            click.echo(f"{info.name:<15} {info.default_model:<25} {is_default}")


if __name__ == "__main__":
    cli()
