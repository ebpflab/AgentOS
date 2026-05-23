"""Sequential Pipeline Workflow — chains agents in order.

Each agent's output becomes the next agent's input.
Supports early termination and step-level error handling.
"""

from __future__ import annotations

import logging
from typing import Any

from agentos.agents.base import ManagedAgent
from agentos.kernel.events import EventBus
from agentos.workflows.templates import BaseWorkflow, WorkflowResult, WorkflowStatus

logger = logging.getLogger(__name__)


class PipelineWorkflow(BaseWorkflow):
    """Sequential agent pipeline: agent₁ → agent₂ → ... → agentₙ.

    Each agent processes the output of the previous agent.

    Usage:
        pipeline = PipelineWorkflow(
            name="translate-and-summarize",
            agents=[translator_agent, summarizer_agent],
        )
        result = await pipeline.run("Long text in French...")
    """

    def __init__(
        self,
        name: str,
        agents: list[ManagedAgent],
        event_bus: EventBus | None = None,
        description: str = "",
    ) -> None:
        super().__init__(name=name, event_bus=event_bus, description=description)
        self._agents = agents

    async def _execute(self, input_data: Any, **kwargs: Any) -> WorkflowResult:
        current_input = str(input_data) if input_data else ""
        steps_completed: list[str] = []

        for i, agent in enumerate(self._agents):
            step_name = f"step_{i}_{agent.name}"

            async def _run_agent(inp: str = current_input, ag: ManagedAgent = agent) -> str:
                return await ag.run(inp)

            try:
                current_input = await self._run_step(step_name, _run_agent)
                steps_completed.append(step_name)
            except Exception as e:
                return WorkflowResult(
                    workflow_id=self._workflow_id,
                    status=WorkflowStatus.FAILED,
                    output=current_input,
                    error=f"Failed at step '{step_name}': {e}",
                    steps_completed=steps_completed,
                )

        return WorkflowResult(
            workflow_id=self._workflow_id,
            status=WorkflowStatus.COMPLETED,
            output=current_input,
            steps_completed=steps_completed,
        )

    @property
    def agent_count(self) -> int:
        return len(self._agents)
