from __future__ import annotations

from contextlib import contextmanager
import logging
from typing import Any, Iterator

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure(endpoint: str, version: str):
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": "forgecart-api",
                "service.version": version,
                "deployment.environment": "regression-demo",
            }
        )
    )
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces"))
            )
        except Exception:
            logging.getLogger("forgecart").exception("OTLP trace exporter unavailable")
    try:
        trace.set_tracer_provider(provider)
    except Exception:
        pass
    return trace.get_tracer("forgecart.checkout", "1.0.0")


@contextmanager
def span(tracer, name: str, attributes: dict[str, Any]) -> Iterator[Any]:
    with tracer.start_as_current_span(name, attributes=attributes) as current:
        try:
            yield current
        except Exception as exc:
            current.record_exception(exc)
            current.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            raise

