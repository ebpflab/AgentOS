"""Workflow templates — base patterns for enterprise workflows.

Provides reusable workflow patterns built on MAF's @workflow/@step
functional API and WorkflowBuilder graph API.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine
from uuid import uuid4

from agentos.agents.base import ManagedAgent
from agentos.kernel.events import Event, EventBus

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SUSPENDED = "suspended"  # Waiting for HITL


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""

    workflow_id: str
    status: WorkflowStatus
    output: Any = None
    error: str = ""
    steps_completed: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


StepFunction = Callable[..., Coroutine[Any, Any, Any]]


@dataclass
class WorkflowStep:
    """A step in a workflow."""

    name: str
    func: StepFunction
    description: str = ""


class BaseWorkflow:
    """Base class for AgentOS workflow templates.

    Provides common infrastructure for workflow execution:
    event publishing, status tracking, error handling.

    Subclasses implement _execute() with the actual workflow logic.
    """

    def __init__(
        self,
        name: str,
        event_bus: EventBus | None = None,
        description: str = "",
    ) -> None:
        self.name = name
        self.description = description
        self._event_bus = event_bus
        self._workflow_id = ""

    async def run(self, input_data: Any = None, **kwargs: Any) -> WorkflowResult:
        """Execute the workflow.

        Args:
            input_data: Input to the workflow.
            **kwargs: Additional parameters.

        Returns:
            WorkflowResult with output and status.
        """
        self._workflow_id = str(uuid4())

        await self._publish_event("workflow.started", {
            "workflow_id": self._workflow_id,
            "name": self.name,
            "input": str(input_data)[:200] if input_data else "",
        })

        try:
            result = await self._execute(input_data, **kwargs)

            if not isinstance(result, WorkflowResult):
                result = WorkflowResult(
                    workflow_id=self._workflow_id,
                    status=WorkflowStatus.COMPLETED,
                    output=result,
                )

            await self._publish_event("workflow.completed", {
                "workflow_id": self._workflow_id,
                "name": self.name,
                "status": result.status.value,
            })

            return result

        except Exception as e:
            logger.exception("Workflow '%s' failed", self.name)
            await self._publish_event("workflow.failed", {
                "workflow_id": self._workflow_id,
                "name": self.name,
                "error": str(e),
            })
            return WorkflowResult(
                workflow_id=self._workflow_id,
                status=WorkflowStatus.FAILED,
                error=str(e),
            )

    async def _execute(self, input_data: Any, **kwargs: Any) -> Any:
        """Override in subclasses with actual workflow logic."""
        raise NotImplementedError

    async def _publish_event(self, topic: str, data: Any) -> None:
        if self._event_bus:
            await self._event_bus.publish(Event(
                topic=topic, data=data, source=f"workflow:{self.name}",
            ))

    async def _run_step(self, step_name: str, func: StepFunction, *args: Any, **kwargs: Any) -> Any:
        """Execute a workflow step with event tracking."""
        await self._publish_event("workflow.step_started", {
            "workflow_id": self._workflow_id,
            "step": step_name,
        })

        try:
            result = await func(*args, **kwargs)
            await self._publish_event("workflow.step_completed", {
                "workflow_id": self._workflow_id,
                "step": step_name,
            })
            return result
        except Exception as e:
            await self._publish_event("workflow.step_failed", {
                "workflow_id": self._workflow_id,
                "step": step_name,
                "error": str(e),
            })
            raise
