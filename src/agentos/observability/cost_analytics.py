"""Cost calculation and reporting.

Maps token usage to USD costs based on configurable model pricing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentos.config import AgentOSConfig


@dataclass
class CostRecord:
    """A single cost record."""

    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float


class CostCalculator:
    """Calculates costs based on model pricing tables.

    Usage:
        calc = CostCalculator(config)
        cost = calc.calculate("openai", "gpt-4.1", input_tokens=1000, output_tokens=500)
        print(f"Cost: ${cost.total_cost:.4f}")
    """

    def __init__(self, config: AgentOSConfig) -> None:
        self._pricing = config.resources.pricing

    def calculate(
        self,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> CostRecord:
        """Calculate cost for token usage."""
        provider_pricing = self._pricing.get(provider, {})
        model_pricing = provider_pricing.get(model)

        if model_pricing is None:
            # Unknown model — zero cost
            return CostRecord(
                provider=provider, model=model,
                input_tokens=input_tokens, output_tokens=output_tokens,
                input_cost=0.0, output_cost=0.0, total_cost=0.0,
            )

        input_cost = (input_tokens / 1000) * model_pricing.input_per_1k
        output_cost = (output_tokens / 1000) * model_pricing.output_per_1k

        return CostRecord(
            provider=provider, model=model,
            input_tokens=input_tokens, output_tokens=output_tokens,
            input_cost=input_cost, output_cost=output_cost,
            total_cost=input_cost + output_cost,
        )

    def get_pricing_table(self) -> dict[str, Any]:
        """Get the full pricing table."""
        return {
            provider: {
                model: {"input_per_1k": p.input_per_1k, "output_per_1k": p.output_per_1k}
                for model, p in models.items()
            }
            for provider, models in self._pricing.items()
        }
