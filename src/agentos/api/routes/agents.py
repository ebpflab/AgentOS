"""Agent CRUD and lifecycle API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agentos.api.deps import require_permission
from agentos.api.server import get_runtime
from agentos.i18n import get_locale, tr
from agentos.security.auth import UserInfo
from agentos.security.rbac import Permission

router = APIRouter()


class AgentCreateRequest(BaseModel):
    name: str
    instructions: str = "You are a helpful assistant."
    provider: str | None = None
    model: str | None = None
    capabilities: list[str] = []
    tags: dict[str, str] = {}


class AgentResponse(BaseModel):
    agent_id: str
    name: str
    status: str
    provider: str
    model: str
    capabilities: list[str]
    tenant_id: str
    tags: dict[str, str] = {}


class AgentRunRequest(BaseModel):
    message: str
    session_id: str | None = None


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    status: str | None = None,
    user: UserInfo = Depends(require_permission(Permission.AGENT_READ)),
):
    """List all agents for the current tenant."""
    runtime = get_runtime()
    from agentos.kernel.registry import AgentStatus
    status_filter = AgentStatus(status) if status else None
    agents = runtime.registry.list_agents(tenant_id=user.tenant_id, status=status_filter)
    return [
        AgentResponse(
            agent_id=a.agent_id, name=a.name, status=a.status.value,
            provider=a.provider, model=a.model, capabilities=a.capabilities,
            tenant_id=a.tenant_id, tags=a.tags,
        )
        for a in agents
    ]


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    req: AgentCreateRequest,
    user: UserInfo = Depends(require_permission(Permission.AGENT_CREATE)),
    locale: str = Depends(get_locale),
):
    """Create a new agent."""
    runtime = get_runtime()
    try:
        agent = await runtime.factory.create(
            name=req.name,
            instructions=req.instructions,
            provider=req.provider,
            model=req.model,
            capabilities=req.capabilities,
            tenant_id=user.tenant_id,
            tags=req.tags,
        )
        return AgentResponse(
            agent_id=agent.agent_id, name=agent.name, status="created",
            provider=agent.provider, model=agent.model,
            capabilities=agent.capabilities, tenant_id=agent.tenant_id,
            tags=agent.tags,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=tr("agent.create_failed", locale, str(e)))


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    user: UserInfo = Depends(require_permission(Permission.AGENT_READ)),
    locale: str = Depends(get_locale),
):
    """Get agent details."""
    runtime = get_runtime()
    meta = runtime.registry.get(agent_id)
    if meta is None or meta.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail=tr("agent.not_found", locale))
    return AgentResponse(
        agent_id=meta.agent_id, name=meta.name, status=meta.status.value,
        provider=meta.provider, model=meta.model, capabilities=meta.capabilities,
        tenant_id=meta.tenant_id, tags=meta.tags,
    )


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    user: UserInfo = Depends(require_permission(Permission.AGENT_DELETE)),
    locale: str = Depends(get_locale),
):
    """Delete an agent."""
    runtime = get_runtime()
    meta = runtime.registry.get(agent_id)
    if meta is None or meta.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail=tr("agent.not_found", locale))
    runtime.registry.unregister(agent_id)


@router.post("/{agent_id}/start")
async def start_agent(
    agent_id: str,
    user: UserInfo = Depends(require_permission(Permission.AGENT_RUN)),
    locale: str = Depends(get_locale),
):
    """Start an agent."""
    runtime = get_runtime()
    meta = runtime.registry.get(agent_id)
    if meta is None or meta.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail=tr("agent.not_found", locale))
    try:
        await runtime.lifecycle.start_agent(agent_id)
        return {"status": "running", "agent_id": agent_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{agent_id}/stop")
async def stop_agent(
    agent_id: str,
    user: UserInfo = Depends(require_permission(Permission.AGENT_RUN)),
    locale: str = Depends(get_locale),
):
    """Stop an agent."""
    runtime = get_runtime()
    meta = runtime.registry.get(agent_id)
    if meta is None or meta.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail=tr("agent.not_found", locale))
    try:
        await runtime.lifecycle.stop_agent(agent_id)
        return {"status": "stopped", "agent_id": agent_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{agent_id}/run")
async def run_agent(
    agent_id: str,
    req: AgentRunRequest,
    user: UserInfo = Depends(require_permission(Permission.AGENT_RUN)),
    locale: str = Depends(get_locale),
):
    """Run an agent with a message. Supports multi-turn conversation via session_id."""
    runtime = get_runtime()
    meta = runtime.registry.get(agent_id)
    if meta is None or meta.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail=tr("agent.not_found", locale))

    instance = runtime.registry.get_instance(agent_id)
    if instance is None:
        raise HTTPException(status_code=400, detail=tr("agent.no_instance", locale))

    # MAF session management — persists conversation context in memory
    # so the agent remembers previous turns.
    _sessions: dict[str, Any] = runtime.registry._sessions

    session = None
    if req.session_id and req.session_id in _sessions:
        session = _sessions[req.session_id]

    if session is None:
        session = instance.create_session()
        sid = getattr(session, "session_id", None)
        if sid:
            _sessions[sid] = session
            req.session_id = sid

    try:
        # Inject shared workflow memory into the message if available
        enriched_message = req.message
        shared_ns = req.session_id or f"agent:{agent_id}"
        ctx = runtime.shared_memory.inject_into_prompt(shared_ns, req.message)
        if ctx != req.message:
            enriched_message = ctx

        result = await instance.run(enriched_message, session=session)
        return {
            "response": str(result),
            "agent_id": agent_id,
            "session_id": getattr(session, "session_id", None),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=tr("common.internal_error", locale, str(e)))
