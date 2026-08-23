import pytest
from pydantic import ValidationError

from forgecart.contracts import broken, fixed, good


PAYLOAD = {
    "customer_name": "Avery Stone",
    "email": "avery@example.com",
    "product_id": "kinetic-driver-01",
    "quantity": 1,
    "total_cents": 12900,
}


def test_good_contract_accepts_storefront_payload():
    assert good.normalize(PAYLOAD)["total_cents"] == 12900


def test_broken_contract_rejects_storefront_payload():
    with pytest.raises(ValidationError):
        broken.normalize(PAYLOAD)


def test_fixed_contract_accepts_old_and_new_names():
    assert fixed.normalize(PAYLOAD)["total_cents"] == 12900
    migrated = {**PAYLOAD, "amount_cents": 12900}
    migrated.pop("total_cents")
    assert fixed.normalize(migrated)["total_cents"] == 12900
