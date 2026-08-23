from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    release: str = os.getenv("FORGECART_RELEASE", "good")
    deployment_version: str = os.getenv("DEPLOYMENT_VERSION", "forgecart-good")
    db_path: str = os.getenv("FORGECART_DB", "data/forgecart.db")
    smtp_host: str = os.getenv("SMTP_HOST", "127.0.0.1")
    smtp_port: int = int(os.getenv("SMTP_PORT", "1025"))
    webhook_url: str = os.getenv(
        "FULFILLMENT_WEBHOOK_URL", "http://127.0.0.1:4400/api/webhooks/fulfillment"
    )
    otlp_endpoint: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")


settings = Settings()

