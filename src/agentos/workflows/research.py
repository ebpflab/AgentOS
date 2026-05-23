"""Parallel Research Workflow — fan-out to multiple agents, fan-in to synthesize.

Sends the same query to N research agents in parallel, then passes
all results to a synthesizer agent for consolidation.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agentos.agents.base import ManagedAgent
from agentos.kernel.events import EventBus
from agentos.workflows.templates import BaseWorkflow, WorkflowResult, WorkflowStatus

logger = logging.getLogger(__name__)


class ResearchWorkflow(BaseWorkflow):
    """Parallel research: fan-out to N agents, fan-in to synthesizer.

    Usage:
        research = ResearchWorkflow(
            name="multi-source-research",
            researchers=[web_agent, papers_agent, news_agent],
            synthesizer=summary_agent,
        )
        result = await research.run("What are the latest advances in quantum computing?")
    """

    def __init__(
        self,
        name: str,
        researchers: list[ManagedAgent],
        synthesizer: ManagedAgent,
        event_bus: EventBus | None = None,
        description: str = "",
        timeout: float = 60.0,
    ) -> None:
        super().__init__(name=name, event_bus=event_bus, description=description)
        self._researchers = researchers
        self._synthesizer = synthesizer
        self._timeout = timeout

    async def _execute(self, input_data: Any, **kwargs: Any) -> WorkflowResult:
        query = str(input_data) if input_data else ""
        steps_completed: list[str] = []

        # Phase 1: Fan-out — run all researchers in parallel
        await self._publish_event("workflow.fanout_started", {
            "workflow_id": self._workflow_id,
            "researcher_count": len(self._researchers),
        })

        async def _research(agent: ManagedAgent) -> tuple[str, str | None]:
            """Run a single researcher, return (agent_name, result_or_none)."""
            try:
                result = await agent.run(query)
                return agent.name, result
            except Exception as e:
                logger.warning("Researcher '%s' failed: %s", agent.name, e)
                return agent.name, None

        # Run all researchers concurrently with timeout
        tasks = [_research(agent) for agent in self._researchers]
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=False),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Research phase timed out after %.1fs", self._timeout)
            results = []

        # Collect successful results
        research_outputs: list[str] = []
        for agent_name, result in results:
            step_name = f"research_{agent_name}"
            if result is not None:
                research_outputs.append(f"[{agent_name}]:\n{result}")
                steps_completed.append(step_name)

        if not research_outputs:
            return WorkflowResult(
                workflow_id=self._workflow_id,
                status=WorkflowStatus.FAILED,
                error="All researchers failed or timed out",
                steps_completed=steps_completed,
            )

        await self._publish_event("workflow.fanout_completed", {
            "workflow_id": self._workflow_id,
            "successful_researchers": len(research_outputs),
            "total_researchers": len(self._researchers),
        })

        # Phase 2: Fan-in — synthesize all results
        synthesis_input = (
            f"Based on the following research results for the query '{query}', "
            f"provide a comprehensive synthesis:\n\n"
            + "\n\n---\n\n".join(research_outputs)
        )

        async def _synthesize() -> str:
            return await self._synthesizer.run(synthesis_input)

        try:
            final_output = await self._run_step("synthesize", _synthesize)
            steps_completed.append("synthesize")
        except Exception as e:
            return WorkflowResult(
                workflow_id=self._workflow_id,
                status=WorkflowStatus.FAILED,
                output=research_outputs,  # Return raw research as fallback
                error=f"Synthesis failed: {e}",
                steps_completed=steps_completed,
            )

        return WorkflowResult(
            workflow_id=self._workflow_id,
            status=WorkflowStatus.COMPLETED,
            output=final_output,
            steps_completed=steps_completed,
            metadata={
                "research_count": len(research_outputs),
                "researcher_count": len(self._researchers),
            },
        )
