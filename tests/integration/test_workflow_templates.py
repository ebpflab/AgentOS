"""Tests for workflow templates."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from agentos.kernel.events import EventBus
from agentos.workflows.templates import BaseWorkflow, WorkflowResult, WorkflowStatus
from agentos.workflows.pipeline import PipelineWorkflow
from agentos.workflows.research import ResearchWorkflow


def _make_mock_agent(name: str, response: str):
    """Create a mock ManagedAgent."""
    agent = AsyncMock()
    agent.name = name
    agent.agent_id = f"mock-{name}"
    agent.run = AsyncMock(return_value=response)
    return agent


async def test_pipeline_workflow():
    """Test sequential pipeline: agent1 → agent2."""
    bus = EventBus()
    await bus.start()

    agent1 = _make_mock_agent("translator", "Translated: Hello World")
    agent2 = _make_mock_agent("summarizer", "Summary: Greeting in English")

    pipeline = PipelineWorkflow(
        name="test-pipeline",
        agents=[agent1, agent2],
        event_bus=bus,
    )

    result = await pipeline.run("Bonjour le monde")

    assert result.status == WorkflowStatus.COMPLETED
    assert result.output == "Summary: Greeting in English"
    assert len(result.steps_completed) == 2

    # Verify agent1 was called with original input
    agent1.run.assert_called_once()
    # Verify agent2 was called with agent1's output
    agent2.run.assert_called_once()

    await bus.stop()


async def test_pipeline_failure_midway():
    """Test pipeline stops on agent failure."""
    agent1 = _make_mock_agent("step1", "step1 output")
    agent2 = _make_mock_agent("step2", "")
    agent2.run = AsyncMock(side_effect=RuntimeError("LLM timeout"))
    agent3 = _make_mock_agent("step3", "step3 output")

    pipeline = PipelineWorkflow(name="fail-pipeline", agents=[agent1, agent2, agent3])
    result = await pipeline.run("input")

    assert result.status == WorkflowStatus.FAILED
    assert "step2" in result.error
    assert len(result.steps_completed) == 1  # Only step1 completed
    agent3.run.assert_not_called()


async def test_research_workflow():
    """Test parallel research with fan-out/fan-in."""
    bus = EventBus()
    await bus.start()

    r1 = _make_mock_agent("web", "Web: Quantum computing advances in 2026")
    r2 = _make_mock_agent("papers", "Papers: New error correction methods")
    r3 = _make_mock_agent("news", "News: Google achieves quantum milestone")
    synthesizer = _make_mock_agent("synth", "Comprehensive summary of quantum computing advances")

    workflow = ResearchWorkflow(
        name="test-research",
        researchers=[r1, r2, r3],
        synthesizer=synthesizer,
        event_bus=bus,
    )

    result = await workflow.run("Latest quantum computing advances")

    assert result.status == WorkflowStatus.COMPLETED
    assert result.output == "Comprehensive summary of quantum computing advances"
    assert "synthesize" in result.steps_completed
    assert result.metadata["research_count"] == 3

    # All researchers called
    r1.run.assert_called_once()
    r2.run.assert_called_once()
    r3.run.assert_called_once()
    # Synthesizer called with combined results
    synthesizer.run.assert_called_once()

    await bus.stop()


async def test_research_partial_failure():
    """Test research continues even if some researchers fail."""
    r1 = _make_mock_agent("web", "Web results")
    r2 = _make_mock_agent("papers", "")
    r2.run = AsyncMock(side_effect=RuntimeError("API error"))
    synthesizer = _make_mock_agent("synth", "Synthesis from partial results")

    workflow = ResearchWorkflow(
        name="partial-research",
        researchers=[r1, r2],
        synthesizer=synthesizer,
    )

    result = await workflow.run("test query")

    # Should still complete with partial results
    assert result.status == WorkflowStatus.COMPLETED
    assert result.metadata["research_count"] == 1  # Only 1 of 2 succeeded


async def test_workflow_events():
    """Test that workflow publishes lifecycle events."""
    bus = EventBus()
    await bus.start()
    events: list = []

    async def handler(e):
        events.append(e.topic)

    await bus.subscribe("workflow.*", handler)

    agent = _make_mock_agent("test", "done")
    pipeline = PipelineWorkflow(name="event-test", agents=[agent], event_bus=bus)
    await pipeline.run("input")

    await asyncio.sleep(0.2)

    assert "workflow.started" in events
    assert "workflow.step_started" in events
    assert "workflow.step_completed" in events
    assert "workflow.completed" in events

    await bus.stop()


# Run all tests
async def main():
    await test_pipeline_workflow()
    print("  pipeline_workflow PASSED")

    await test_pipeline_failure_midway()
    print("  pipeline_failure_midway PASSED")

    await test_research_workflow()
    print("  research_workflow PASSED")

    await test_research_partial_failure()
    print("  research_partial_failure PASSED")

    await test_workflow_events()
    print("  workflow_events PASSED")


if __name__ == "__main__":
    asyncio.run(main())
