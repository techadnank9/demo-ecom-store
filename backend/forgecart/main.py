from __future__ import annotations

from email.message import EmailMessage
import json
import logging
import smtplib
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from pydantic import ValidationError

from .config import settings
from .contracts import load_contract
from .database import OrderStore, TelemetryAudit
from .telemetry import configure, span


PRODUCT = {
    "id": "kinetic-driver-01",
    "name": "Kinetic Driver",
    "description": "A precision ratcheting driver milled for the workbench.",
    "price_cents": 12900,
}

app = FastAPI(title="ForgeCart", version=settings.deployment_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-trace-id", "x-regressionforge-run-id", "x-deployment-version"],
)
orders = OrderStore(settings.db_path)
tracer = configure(settings.otlp_endpoint, settings.deployment_version)
audit = TelemetryAudit(settings.db_path, settings.deployment_version)
contract = load_contract(settings.release)
logger = logging.getLogger("forgecart")


@app.middleware("http")
async def correlation_headers(request: Request, call_next):
    run_id = request.headers.get("x-regressionforge-run-id", "untracked")
    response = await call_next(request)
    response.headers["x-regressionforge-run-id"] = run_id
    response.headers["x-deployment-version"] = settings.deployment_version
    return response


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "forgecart-api",
        "release": settings.release,
        "deployment_version": settings.deployment_version,
    }


@app.get("/api/products")
def products() -> list[dict]:
    return [PRODUCT]


@app.post("/api/checkout")
async def checkout(
    request: Request,
    x_regressionforge_run_id: str = Header(default="untracked"),
    x_deployment_version: str | None = Header(default=None),
):
    run_id = x_regressionforge_run_id
    version = x_deployment_version or settings.deployment_version
    attributes = {"regression.run_id": run_id, "deployment.version": version}
    with span(tracer, "forgecart.checkout", attributes):
        payload = await request.json()
        try:
            normalized = contract.normalize(payload)
        except ValidationError as exc:
            audit.emit(
                "checkout.contract_error",
                severity="ERROR",
                run_id=run_id,
                deployment_version=version,
                release=settings.release,
                error_type="CheckoutContractValidationError",
                error=str(exc),
                received_fields=sorted(payload.keys()),
                expected_field=getattr(contract, "EXPECTED_FIELD", "checkout amount"),
            )
            logger.exception("Checkout contract validation failed for run %s", run_id)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "checkout_contract_failed",
                    "message": "Checkout could not be completed.",
                    "run_id": run_id,
                    "deployment_version": version,
                },
            )

        if normalized["product_id"] != PRODUCT["id"]:
            raise HTTPException(status_code=404, detail="Product not found")
        expected_total = PRODUCT["price_cents"] * normalized["quantity"]
        if normalized["total_cents"] != expected_total:
            raise HTTPException(status_code=409, detail="Price changed; refresh checkout")

        order_id = f"F-{uuid4().hex[:8].upper()}"
        order = orders.create(order_id, run_id, version, normalized)
        audit.emit(
            "checkout.order_persisted",
            severity="INFO",
            run_id=run_id,
            deployment_version=version,
            order_id=order_id,
        )

        await _send_confirmation(order)
        await _notify_fulfillment(order)
        return {"order": order, "message": "Order confirmed"}


async def _send_confirmation(order: dict) -> None:
    message = EmailMessage()
    message["Subject"] = f"ForgeCart order {order['id']} confirmed"
    message["From"] = "orders@forgecart.test"
    message["To"] = order["email"]
    message["X-RegressionForge-Run-ID"] = order["run_id"]
    message.set_content(
        f"Thanks {order['customer_name']}. Your order {order['id']} is confirmed.\n"
        f"Regression run: {order['run_id']}"
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
            smtp.send_message(message)
        audit.emit(
            "checkout.email_sent", severity="INFO", run_id=order["run_id"], order_id=order["id"]
        )
    except Exception as exc:
        audit.emit(
            "checkout.email_failed",
            severity="ERROR",
            run_id=order["run_id"],
            order_id=order["id"],
            error=str(exc),
        )
        raise HTTPException(status_code=502, detail="Confirmation email failed") from exc


async def _notify_fulfillment(order: dict) -> None:
    headers = {
        "x-regressionforge-run-id": order["run_id"],
        "x-deployment-version": order["deployment_version"],
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(
                settings.webhook_url,
                json={"event": "order.ready_for_fulfillment", "order": order},
                headers=headers,
            )
            response.raise_for_status()
        audit.emit(
            "checkout.webhook_sent", severity="INFO", run_id=order["run_id"], order_id=order["id"]
        )
    except Exception as exc:
        audit.emit(
            "checkout.webhook_failed",
            severity="ERROR",
            run_id=order["run_id"],
            order_id=order["id"],
            error=str(exc),
        )
        raise HTTPException(status_code=502, detail="Fulfillment notification failed") from exc


@app.get("/api/orders")
def list_orders(run_id: str | None = None) -> list[dict]:
    return orders.list(run_id)


@app.get("/api/telemetry/logs")
def telemetry_logs(run_id: str) -> dict:
    return {"source": "local_otel_audit", "run_id": run_id, "records": audit.query(run_id)}


@app.post("/api/admin/reset")
def reset() -> dict:
    orders.reset()
    return {"status": "reset"}
