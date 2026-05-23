"""Workflow management API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agentos.api.deps import require_permission
from agentos.i18n import get_locale, tr
from agentos.security.auth import UserInfo
from agentos.security.rbac import Permission

router = APIRouter()


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
    """Run a workflow."""
    # For now, return a placeholder — full implementation in production
    return WorkflowStatusResponse(
        workflow_id="pending",
        status="pending",
        error=tr("workflow.requires_instances", locale),
    )


@router.get("/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    workflow_id: str,
    user: UserInfo = Depends(require_permission(Permission.WORKFLOW_READ)),
    locale: str = Depends(get_locale),
):
    """Get workflow execution status."""
    raise HTTPException(status_code=404, detail=tr("workflow.not_found", locale))


@router.post("/{workflow_id}/resume")
async def resume_workflow(
    workflow_id: str,
    approval: dict = {},
    user: UserInfo = Depends(require_permission(Permission.WORKFLOW_RUN)),
    locale: str = Depends(get_locale),
):
    """Resume a suspended workflow (HITL approval)."""
    raise HTTPException(status_code=404, detail=tr("workflow.not_found", locale))
