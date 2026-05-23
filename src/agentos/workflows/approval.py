"""HITL Approval Chain Workflow.

Suspends execution at approval points, resumes when approved.
Uses MAF's ctx.request_info() pattern conceptually.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agentos.agents.base import ManagedAgent
from agentos.kernel.events import EventBus
from agentos.workflows.templates import BaseWorkflow, WorkflowResult, WorkflowStatus

logger = logging.getLogger(__name__)


class ApprovalWorkflow(BaseWorkflow):
    """Workflow with human-in-the-loop approval gates.

    Runs an agent, then suspends for approval. If approved, passes
    the output to the next stage. If rejected, terminates.

    Usage:
        wf = ApprovalWorkflow(
            name="draft-review",
            draft_agent=writer_agent,
            final_agent=publisher_agent,
            event_bus=bus,
        )
        result = await wf.run("Write a blog post about AI")
        # result.status == SUSPENDED if waiting for approval
        # Call resume(approval_data) to continue
    """

    def __init__(
        self,
        name: str,
        draft_agent: ManagedAgent,
        final_agent: ManagedAgent | None = None,
        event_bus: EventBus | None = None,
        description: str = "",
    ) -> None:
        super().__init__(name=name, event_bus=event_bus, description=description)
        self._draft_agent = draft_agent
        self._final_agent = final_agent
        self._pending_approval: dict[str, Any] = {}  # workflow_id -> draft output
        self._approval_events: dict[str, asyncio.Event] = {}
        self._approval_decisions: dict[str, dict] = {}

    async def _execute(self, input_data: Any, **kwargs: Any) -> WorkflowResult:
        steps_completed = []

        # Step 1: Generate draft
        async def _draft():
            return await self._draft_agent.run(str(input_data))

        draft = await self._run_step("generate_draft", _draft)
        steps_completed.append("generate_draft")

        # Step 2: Request approval (suspend)
        self._pending_approval[self._workflow_id] = draft
        approval_event = asyncio.Event()
        self._approval_events[self._workflow_id] = approval_event

        await self._publish_event("workflow.approval_requested", {
            "workflow_id": self._workflow_id,
            "draft": str(draft)[:500],
            "instructions": "Please review and approve or reject this draft.",
        })

        # Check if there's a pre-set approval (for testing or resumed workflows)
        if self._workflow_id in self._approval_decisions:
            decision = self._approval_decisions.pop(self._workflow_id)
        else:
            return WorkflowResult(
                workflow_id=self._workflow_id,
                status=WorkflowStatus.SUSPENDED,
                output=draft,
                steps_completed=steps_completed,
                metadata={"pending_approval": True},
            )

        return await self._process_decision(draft, decision, steps_completed)

    async def resume(self, workflow_id: str, decision: dict) -> WorkflowResult:
        """Resume a suspended workflow with an approval decision.

        Args:
            workflow_id: The workflow to resume.
            decision: {"approved": True/False, "feedback": "optional feedback"}
        """
        draft = self._pending_approval.get(workflow_id)
        if draft is None:
            return WorkflowResult(
                workflow_id=workflow_id,
                status=WorkflowStatus.FAILED,
                error="No pending approval for this workflow",
            )

        self._workflow_id = workflow_id
        return await self._process_decision(draft, decision, ["generate_draft"])

    async def _process_decision(
        self, draft: str, decision: dict, steps_completed: list[str]
    ) -> WorkflowResult:
        approved = decision.get("approved", False)
        feedback = decision.get("feedback", "")

        self._pending_approval.pop(self._workflow_id, None)
        self._approval_events.pop(self._workflow_id, None)

        if not approved:
            await self._publish_event("workflow.approval_rejected", {
                "workflow_id": self._workflow_id,
                "feedback": feedback,
            })
            return WorkflowResult(
                workflow_id=self._workflow_id,
                status=WorkflowStatus.COMPLETED,
                output=f"Rejected: {feedback}" if feedback else "Rejected by reviewer",
                steps_completed=steps_completed + ["approval_rejected"],
            )

        # Step 3: Finalize (if final agent provided)
        if self._final_agent:
            final_input = f"Approved draft:\n{draft}"
            if feedback:
                final_input += f"\n\nFeedback: {feedback}"

            async def _finalize():
                return await self._final_agent.run(final_input)

            final_output = await self._run_step("finalize", _finalize)
            steps_completed.append("finalize")
        else:
            final_output = draft

        return WorkflowResult(
            workflow_id=self._workflow_id,
            status=WorkflowStatus.COMPLETED,
            output=final_output,
            steps_completed=steps_completed + ["approved"],
        )
