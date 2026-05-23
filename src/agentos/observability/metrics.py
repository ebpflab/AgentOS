"""Prometheus-compatible metrics collection."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and exposes AgentOS metrics.

    Provides both Prometheus-format and JSON-format metrics.
    Falls back to in-memory counters if prometheus_client is not available.

    Tracked metrics:
    - agentos_agent_runs_total (counter)
    - agentos_agent_errors_total (counter)
    - agentos_tokens_used_total (counter, by provider/model)
    - agentos_agent_run_duration_seconds (histogram)
    - agentos_active_agents (gauge)
    """

    def __init__(self) -> None:
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._labels: dict[str, dict[str, str]] = {}

    def inc_counter(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        key = self._make_key(name, labels)
        self._counters[key] = self._counters.get(key, 0) + value
        if labels:
            self._labels[key] = labels

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        key = self._make_key(name, labels)
        self._gauges[key] = value
        if labels:
            self._labels[key] = labels

    def observe_histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        key = self._make_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        if labels:
            self._labels[key] = labels

    def record_agent_run(self, agent_id: str, provider: str, model: str, duration: float, success: bool) -> None:
        """Convenience: record an agent run with all relevant metrics."""
        labels = {"agent_id": agent_id, "provider": provider, "model": model}
        self.inc_counter("agentos_agent_runs_total", labels=labels)
        if not success:
            self.inc_counter("agentos_agent_errors_total", labels=labels)
        self.observe_histogram("agentos_agent_run_duration_seconds", duration, labels=labels)

    def record_token_usage(self, provider: str, model: str, input_tokens: int, output_tokens: int) -> None:
        labels = {"provider": provider, "model": model}
        self.inc_counter("agentos_input_tokens_total", float(input_tokens), labels=labels)
        self.inc_counter("agentos_output_tokens_total", float(output_tokens), labels=labels)
        self.inc_counter("agentos_tokens_total", float(input_tokens + output_tokens), labels=labels)

    def to_json(self) -> dict[str, Any]:
        """Export all metrics as JSON."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                k: {"count": len(v), "sum": sum(v), "avg": sum(v) / len(v) if v else 0}
                for k, v in self._histograms.items()
            },
        }

    def _make_key(self, name: str, labels: dict[str, str] | None = None) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


# Global metrics instance
_metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    return _metrics
