from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Any


class OrderStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    deployment_version TEXT NOT NULL,
                    customer_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    total_cents INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )

    def create(self, order_id: str, run_id: str, deployment_version: str, payload: dict) -> dict:
        order = {
            "id": order_id,
            "run_id": run_id,
            "deployment_version": deployment_version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO orders
                (id, run_id, deployment_version, customer_name, email, product_id, quantity, total_cents, created_at)
                VALUES (:id, :run_id, :deployment_version, :customer_name, :email, :product_id, :quantity, :total_cents, :created_at)""",
                order,
            )
        return order

    def list(self, run_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM orders"
        params: tuple[str, ...] = ()
        if run_id:
            query += " WHERE run_id = ?"
            params = (run_id,)
        query += " ORDER BY created_at DESC"
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(query, params).fetchall()]

    def reset(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM orders")


class TelemetryAudit:
    def __init__(self, db_path: str, deployment_version: str):
        self.path = Path(db_path).with_name("forgecart-telemetry.jsonl")
        self.deployment_version = deployment_version
        self._lock = RLock()

    def emit(self, event: str, **attributes: Any) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "forgecart-api",
            "event": event,
            **attributes,
        }
        with self._lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        from .telemetry import emit_audit_log

        emit_audit_log(event, self.deployment_version, attributes)

    def query(self, run_id: str) -> list[dict]:
        if not self.path.exists():
            return []
        results = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("run_id") == run_id:
                results.append(record)
        return results
