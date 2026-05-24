"""Workflow management API routes.

Supports executing sequential pipelines, parallel research, approval
chains, and escalation workflows using real MAF agent instances.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agentos.api.deps import require_permission
from agentos.api.server import get_runtime
from agentos.i18n import get_locale, tr
from agentos.security.auth import UserInfo
from agentos.security.rbac import Permission

router = APIRouter()

# Track workflow execution results in memory
_runs: dict[str, dict] = {}


class WorkflowRunRequest(BaseModel):
    workflow_name: str
    input_data: str = ""
    agent_names: list[str] = []
    parameters: dict = {}


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    status: str
    output: str | None = None
    error: str = ""
    steps_completed: list[str] = []


@router.post("/run", response_model=WorkflowStatusResponse)
async def run_workflow(
    req: WorkflowRunRequest,
    user: UserInfo = Depends(require_permission(Permission.WORKFLOW_RUN)),
    locale: str = Depends(get_locale),
):
    """Run a workflow using real agent instances.

    The workflow picks agents whose names match ``agent_names`` from the
    registry.  Agents must be running (have an active MAF instance).
    """
    runtime = get_runtime()
    wf_type = req.workflow_name

    # Find the requested agents
    agents: list = []
    for name in (req.agent_names or []):
        meta = runtime.registry.find_by_name(name)
        if meta is None:
            raise HTTPException(
                status_code=400,
                detail=f"Agent not found: '{name}'",
            )
        inst = runtime.registry.get_instance(meta.agent_id)
        if inst is None:
            raise HTTPException(
                status_code=400,
                detail=f"Agent '{name}' has no active instance. Start it first.",
            )
        agents.append(inst)

    from agentos.workflows.templates import WorkflowStatus

    # If no agents specified, auto-discover running agents
    if not agents:
        from agentos.kernel.registry import AgentStatus
        for meta in runtime.registry.list_agents(status=AgentStatus.RUNNING):
            inst = runtime.registry.get_instance(meta.agent_id)
            if inst is not None:
                agents.append(inst)
        if not agents:
            return WorkflowStatusResponse(
                workflow_id="none",
                status="failed",
                error=tr("workflow.requires_instances", locale),
            )

    wf_id = str(uuid.uuid4())[:12]
    _runs[wf_id] = {"status": "running", "steps": []}

    # Execute the appropriate workflow type
    try:
        if wf_type == "pipeline":
            result = await _run_pipeline(wf_id, agents, req.input_data)
        elif wf_type == "research":
            result = await _run_research(wf_id, agents, req.input_data)
        elif wf_type == "approval":
            result = await _run_approval(wf_id, agents, req.input_data)
        elif wf_type == "escalation":
            result = await _run_escalation(wf_id, agents, req.input_data)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown workflow type: '{wf_type}'")

        _runs[wf_id] = {
            "status": result["status"],
            "output": result.get("output"),
            "steps": result.get("steps_completed", []),
        }

        return WorkflowStatusResponse(
            workflow_id=wf_id,
            status=result["status"],
            output=result.get("output"),
            error=result.get("error", ""),
            steps_completed=result.get("steps_completed", []),
        )
    except Exception as e:
        _runs[wf_id] = {"status": "failed", "error": str(e)}
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    workflow_id: str,
    user: UserInfo = Depends(require_permission(Permission.WORKFLOW_READ)),
    locale: str = Depends(get_locale),
):
    """Get workflow execution status."""
    run = _runs.get(workflow_id)
    if run is None:
        raise HTTPException(status_code=404, detail=tr("workflow.not_found", locale))
    return WorkflowStatusResponse(
        workflow_id=workflow_id,
        status=run.get("status", "unknown"),
        output=run.get("output"),
        error=run.get("error", ""),
        steps_completed=run.get("steps", []),
    )


@router.post("/{workflow_id}/resume")
async def resume_workflow(
    workflow_id: str,
    approval: dict = {},
    user: UserInfo = Depends(require_permission(Permission.WORKFLOW_RUN)),
    locale: str = Depends(get_locale),
):
    """Resume a suspended workflow (HITL approval)."""
    raise HTTPException(status_code=404, detail=tr("workflow.not_found", locale))


# ── Workflow runners ─────────────────────────────────────────────

async def _run_pipeline(wf_id: str, agents: list, inp: str) -> dict:
    """Run agents sequentially: A → B → C."""
    current = inp or "Process this input"
    steps = []
    for ag in agents:
        name = getattr(ag, "name", "agent")
        try:
            resp = await ag.run(current)
            current = str(resp)
            steps.append(str(name))
        except Exception as e:
            return {"status": "failed", "output": current, "error": str(e), "steps_completed": steps}
    return {"status": "completed", "output": current, "steps_completed": steps}


async def _run_research(wf_id: str, agents: list, inp: str) -> dict:
    """Fan-out to N researchers, then synthesize."""
    import asyncio

    if len(agents) < 2:
        return {"status": "failed", "error": "Research workflow needs at least 2 agents", "steps_completed": []}

    researchers = agents[:-1]
    synthesizer = agents[-1]

    async def research(ag, topic):
        return str(await ag.run(f"Research this topic and provide your findings: {topic}"))

    results = await asyncio.gather(*[research(ag, inp or "analyze this") for ag in researchers])
    combined = "\n\n".join(f"Researcher {i+1}:\n{r}" for i, r in enumerate(results))
    final = str(await synthesizer.run(f"Synthesize the following research results into a unified report:\n\n{combined}"))
    return {"status": "completed", "output": final, "steps_completed": [a.name for a in agents]}


async def _run_approval(wf_id: str, agents: list, inp: str) -> dict:
    """Draft → review (simplified — full HITL needs session support)."""
    if len(agents) < 2:
        return {"status": "failed", "error": "Approval workflow needs at least 2 agents", "steps_completed": []}

    drafter, reviewer = agents[0], agents[1]
    draft = str(await drafter.run(f"Draft a proposal for: {inp or 'the task'}"))
    review = str(await reviewer.run(f"Review this draft and approve or request changes:\n\n{draft}"))
    return {"status": "completed", "output": review, "steps_completed": [drafter.name, reviewer.name]}


async def _run_escalation(wf_id: str, agents: list, inp: str) -> dict:
    """Try agents in escalation order; move to next on failure."""
    for ag in agents:
        try:
            resp = str(await ag.run(inp or "process this"))
            return {"status": "completed", "output": resp, "steps_completed": [ag.name]}
        except Exception:
            continue
    return {"status": "failed", "error": "All agents in escalation chain failed", "steps_completed": []}
