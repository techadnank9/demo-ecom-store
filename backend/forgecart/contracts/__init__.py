from __future__ import annotations

from importlib import import_module
from typing import Protocol


class CheckoutContract(Protocol):
    @staticmethod
    def normalize(payload: dict) -> dict: ...


def load_contract(release: str) -> CheckoutContract:
    safe_release = release if release in {"good", "broken", "fixed"} else "good"
    return import_module(f"forgecart.contracts.{safe_release}")  # type: ignore[return-value]

