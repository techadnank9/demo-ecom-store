from pydantic import BaseModel, EmailStr, Field


class CheckoutPayload(BaseModel):
    """The incompatible v2 contract intentionally used by the broken release."""

    customer_name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    product_id: str
    quantity: int = Field(ge=1, le=5)
    amount_cents: int = Field(gt=0)


def normalize(payload: dict) -> dict:
    normalized = CheckoutPayload.model_validate(payload).model_dump()
    normalized["total_cents"] = normalized.pop("amount_cents")
    return normalized

