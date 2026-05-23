# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgentOS is an enterprise-grade Agent Operating System built on top of Microsoft Agent Framework (MAF) v1.6.0. MAF is the successor to both AutoGen and Semantic Kernel. AgentOS manages agent lifecycle, inter-agent communication, resource budgets, security/multi-tenancy, and workflow orchestration.

**Languages:** Python (primary), React/TypeScript (web UI — Phase 5)
**MAF docs:** https://learn.microsoft.com/en-us/agent-framework/
**MAF repo:** https://github.com/microsoft/agent-framework

## Build & Development Commands

```bash
# Install
pip install -e ".[dev]"

# Run tests (pytest or inline scripts)
PYTHONPATH=src pytest tests/
PYTHONPATH=src pytest tests/unit/test_registry.py -k "test_find_by_capability"
PYTHONPATH=src python tests/integration/test_agent_communication.py
PYTHONPATH=src python tests/integration/test_workflow_templates.py

# Lint
ruff check src/ tests/
ruff format src/ tests/

# CLI
PYTHONPATH=src python -m agentos --help
PYTHONPATH=src python -m agentos start                    # Start API server (FastAPI + uvicorn)
PYTHONPATH=src python -m agentos agents list
PYTHONPATH=src python -m agentos agents create -n MyAgent -p openai -m gpt-4.1
PYTHONPATH=src python -m agentos providers list

# Docker
docker-compose up -d                                       # PostgreSQL + Redis + API
```

## Architecture (54 source files)

```
src/agentos/
├── kernel/              # Core OS runtime
│   ├── runtime.py       # AgentOSRuntime — central coordinator, boots all subsystems
│   ├── registry.py      # AgentRegistry — capability-based discovery, tenant-scoped
│   ├── lifecycle.py     # LifecycleManager — CREATED→STARTING→RUNNING→STOPPING→STOPPED→ERROR
│   └── events.py        # EventBus — async pub/sub with fnmatch wildcard topics
├── providers/
│   └── manager.py       # ProviderManager — resolves (provider, model) → MAF ChatClient
├── agents/
│   ├── base.py          # ManagedAgent — wraps MAF Agent + agent_id, status, capabilities
│   ├── factory.py       # AgentFactory — from code or YAML, auto-registers in registry
│   ├── router.py        # RouterAgent — dispatches tasks by capability match
│   └── supervisor.py    # SupervisorAgent — monitors health, auto-restarts failures
├── communication/
│   ├── protocols.py     # AgentMessage dataclass, MessageType, ConversationContext
│   ├── bus.py           # MessageBus — direct/broadcast/request-reply messaging
│   └── a2a_bridge.py    # Bridge to MAF A2A protocol for remote agents
├── workflows/
│   ├── templates.py     # BaseWorkflow with event tracking and error handling
│   ├── pipeline.py      # Sequential: agent₁ → agent₂ → ... → agentₙ
│   ├── research.py      # Fan-out to N researchers, fan-in to synthesizer
│   ├── approval.py      # HITL approval gates with suspend/resume
│   └── escalation.py    # Agent → senior → human with timeout-based escalation
├── memory/
│   ├── store.py         # MemoryStore Protocol (structural subtyping)
│   ├── shared_kb.py     # Namespace-scoped KB: {tenant}/shared/{key}, {tenant}/{agent}/{key}
│   ├── context_providers.py  # MAF ContextProvider for memory injection
│   └── backends/
│       ├── memory_backend.py    # In-memory with TTL (dev)
│       └── postgres_backend.py  # PostgreSQL + pgvector
├── resources/
│   ├── budget.py        # BudgetManager — per-agent/tenant token limits
│   ├── rate_limiter.py  # Sliding window rate limiter
│   └── quota.py         # QuotaDefinition per tenant
├── security/
│   ├── auth.py          # OAuth2/OIDC SSO (Azure AD, Okta, Keycloak)
│   ├── rbac.py          # Roles (admin/operator/viewer/agent) → 13 permissions
│   ├── tenant.py        # TenantContext via contextvars
│   ├── audit.py         # Structured audit logging
│   └── credentials.py   # Credential vault (env, config, composite)
├── middleware/
│   ├── auth_mw.py       # JWT validation → UserInfo → TenantContext
│   ├── budget_mw.py     # Token budget enforcement wrapping LLM calls
│   ├── audit_mw.py      # Tool invocation audit trail
│   ├── tenant_mw.py     # Tenant context injection
│   └── logging_mw.py    # Structured JSON request logging
├── observability/
│   ├── telemetry.py     # OpenTelemetry TracerProvider setup
│   ├── metrics.py       # Prometheus-compatible counters/histograms/gauges
│   └── cost_analytics.py # Model pricing table → cost per agent/tenant
├── db/
│   ├── models.py        # 7 SQLAlchemy tables: tenants, agents, sessions, token_usage, audit_log, workflow_runs, messages
│   ├── session.py       # Async engine factory, session context manager
│   └── repositories.py  # CRUD repos for all entities
├── api/
│   ├── server.py        # FastAPI app with lifespan (boot/shutdown runtime)
│   ├── deps.py          # DI: get_current_user, require_permission
│   ├── websocket.py     # WebSocket for real-time event streaming
│   └── routes/          # 6 route modules: agents, workflows, sessions, metrics, auth, admin
└── cli.py               # Click CLI: start, agents, providers
```

## Key Design Patterns

- **Runtime as coordinator:** `AgentOSRuntime` holds refs to EventBus, Registry, Lifecycle, ProviderManager, MessageBus, Supervisor, Factory
- **Capability discovery:** Agents register capabilities, `RouterAgent` and `registry.find_by_capability()` match tasks to agents
- **Event-driven:** All lifecycle changes, messages, and workflow steps publish to EventBus → WebSocket → UI
- **Tenant isolation:** `TenantContext` (via contextvars) scopes every operation; middleware enforces at API boundary
- **Protocol-based storage:** `MemoryStore` is a Python Protocol — backends implement without inheritance

## MAF Integration Points

| AgentOS Layer | MAF Feature |
|---|---|
| Agent creation | `client.as_agent(name, instructions)` |
| Agent composition | `.as_tool()` to use agents as tools |
| Workflows | `@workflow`/`@step` (functional) or `WorkflowBuilder` (graph) |
| HITL | `ctx.request_info()` suspends workflow for human approval |
| Memory | `ContextProvider.before_run()` injects memory |
| Security | `@agent_middleware`, `@function_middleware`, `@chat_middleware` |
| Providers | `agent-framework-openai`, `agent-framework-anthropic`, `agent-framework-ollama` |

## API Endpoints (27 routes)

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | System health |
| POST | /api/agents | Create agent |
| GET | /api/agents | List agents |
| GET | /api/agents/{id} | Get agent details |
| DELETE | /api/agents/{id} | Delete agent |
| POST | /api/agents/{id}/start | Start agent |
| POST | /api/agents/{id}/stop | Stop agent |
| POST | /api/agents/{id}/run | Run agent with message |
| POST | /api/workflows/run | Execute workflow |
| GET | /api/workflows/{id}/status | Workflow status |
| POST | /api/workflows/{id}/resume | Resume HITL workflow |
| GET | /api/metrics/agents | Agent metrics |
| GET | /api/metrics/cost | Cost analytics |
| GET | /api/metrics/tokens | Token usage |
| POST | /api/auth/login | Login (dev mode) |
| WS | /ws/events | Real-time event stream |
