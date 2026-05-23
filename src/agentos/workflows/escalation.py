"""Escalation Workflow — agent → senior agent → human.

Tries progressively more capable agents. If all fail or timeout,
escalates to a human review.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agentos.agents.base import ManagedAgent
from agentos.kernel.events import EventBus
from agentos.workflows.templates import BaseWorkflow, WorkflowResult, WorkflowStatus

logger = logging.getLogger(__name__)


class EscalationWorkflow(BaseWorkflow):
    """Escalation chain: tries agents in order with timeouts.

    Each agent gets a chance to handle the task. If it fails or times out,
    the task escalates to the next agent. If all agents fail, it returns
    a "needs human review" result.

    Usage:
        wf = EscalationWorkflow(
            name="support-escalation",
            agents=[junior_agent, senior_agent, expert_agent],
            timeout_per_agent=30.0,
        )
        result = await wf.run("Complex customer issue...")
    """

    def __init__(
        self,
        name: str,
        agents: list[ManagedAgent],
        event_bus: EventBus | None = None,
        timeout_per_agent: float = 30.0,
        description: str = "",
    ) -> None:
        super().__init__(name=name, event_bus=event_bus, description=description)
        self._agents = agents
        self._timeout = timeout_per_agent

    async def _execute(self, input_data: Any, **kwargs: Any) -> WorkflowResult:
        query = str(input_data) if input_data else ""
        steps_completed: list[str] = []
        escalation_log: list[dict] = []

        for i, agent in enumerate(self._agents):
            level = f"level_{i}_{agent.name}"

            await self._publish_event("workflow.escalation_attempt", {
                "workflow_id": self._workflow_id,
                "level": i,
                "agent": agent.name,
            })

            try:
                async def _try_agent(ag=agent, q=query):
                    return await ag.run(q)

                result = await asyncio.wait_for(
                    self._run_step(level, _try_agent),
                    timeout=self._timeout,
                )

                steps_completed.append(level)
                escalation_log.append({
                    "level": i, "agent": agent.name, "outcome": "success",
                })

                return WorkflowResult(
                    workflow_id=self._workflow_id,
                    status=WorkflowStatus.COMPLETED,
                    output=result,
                    steps_completed=steps_completed,
                    metadata={
                        "resolved_by": agent.name,
                        "escalation_level": i,
                        "escalation_log": escalation_log,
                    },
                )

            except asyncio.TimeoutError:
                logger.warning("Agent '%s' timed out after %.1fs", agent.name, self._timeout)
                escalation_log.append({
                    "level": i, "agent": agent.name, "outcome": "timeout",
                })
                steps_completed.append(f"{level}_timeout")

            except Exception as e:
                logger.warning("Agent '%s' failed: %s", agent.name, e)
                escalation_log.append({
                    "level": i, "agent": agent.name, "outcome": "error", "error": str(e),
                })
                steps_completed.append(f"{level}_error")

        # All agents exhausted — needs human review
        await self._publish_event("workflow.escalation_exhausted", {
            "workflow_id": self._workflow_id,
            "levels_tried": len(self._agents),
        })

        return WorkflowResult(
            workflow_id=self._workflow_id,
            status=WorkflowStatus.SUSPENDED,
            output=None,
            error="All agents exhausted — requires human review",
            steps_completed=steps_completed,
            metadata={"escalation_log": escalation_log, "needs_human_review": True},
        )
