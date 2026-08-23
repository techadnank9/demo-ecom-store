from __future__ import annotations

from contextlib import contextmanager
import json
import logging
from typing import Any, Iterator

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


_audit_logger = logging.getLogger("forgecart.audit")


def configure(endpoint: str, version: str):
    resource = Resource.create(
        {
            "service.name": "forgecart-api",
            "service.version": version,
            "deployment.environment": "regression-demo",
        }
    )
    provider = TracerProvider(resource=resource)
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces"))
            )
        except Exception:
            logging.getLogger("forgecart").exception("OTLP trace exporter unavailable")
        try:
            from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
            from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
            from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor

            log_provider = LoggerProvider(resource=resource)
            log_provider.add_log_record_processor(
                SimpleLogRecordProcessor(
                    OTLPLogExporter(endpoint=f"{endpoint.rstrip('/')}/v1/logs")
                )
            )
            _audit_logger.handlers.clear()
            _audit_logger.addHandler(LoggingHandler(logger_provider=log_provider))
            _audit_logger.setLevel(logging.INFO)
            _audit_logger.propagate = False
        except Exception:
            logging.getLogger("forgecart").exception("OTLP log exporter unavailable")
    try:
        trace.set_tracer_provider(provider)
    except Exception:
        pass
    return trace.get_tracer("forgecart.checkout", "1.0.0")


def emit_audit_log(event: str, version: str, attributes: dict[str, Any]) -> None:
    """Emit the same audit record to OTel without placing secrets in log attributes."""
    severity = str(attributes.get("severity", "INFO")).upper()
    run_id = str(attributes.get("run_id", "untracked"))
    body = json.dumps(
        {"event": event, **attributes},
        sort_keys=True,
        default=str,
    )
    extra = {
        "event.name": event,
        "regression.run_id": run_id,
        "deployment.version": str(attributes.get("deployment_version", version)),
    }
    if severity == "ERROR":
        _audit_logger.error(body, extra=extra)
    elif severity == "WARNING":
        _audit_logger.warning(body, extra=extra)
    else:
        _audit_logger.info(body, extra=extra)


@contextmanager
def span(tracer, name: str, attributes: dict[str, Any]) -> Iterator[Any]:
    with tracer.start_as_current_span(name, attributes=attributes) as current:
        try:
            yield current
        except Exception as exc:
            current.record_exception(exc)
            current.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            raise
