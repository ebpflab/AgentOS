"""OpenTelemetry setup for distributed tracing."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def setup_telemetry(otlp_endpoint: str = "", service_name: str = "agentos") -> Any | None:
    """Initialize OpenTelemetry tracing.

    Args:
        otlp_endpoint: OTLP exporter endpoint (empty = no export).
        service_name: Service name for traces.

    Returns:
        TracerProvider or None if OpenTelemetry not available.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        if otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                provider.add_span_processor(BatchSpanProcessor(exporter))
                logger.info("OTLP trace exporter configured: %s", otlp_endpoint)
            except ImportError:
                logger.warning("OTLP exporter not available, using console exporter")
                provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        else:
            logger.info("No OTLP endpoint configured — tracing to console only")

        trace.set_tracer_provider(provider)
        return provider

    except ImportError:
        logger.info("OpenTelemetry not installed — tracing disabled")
        return None


def get_tracer(name: str = "agentos"):
    """Get an OpenTelemetry tracer."""
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        return None
