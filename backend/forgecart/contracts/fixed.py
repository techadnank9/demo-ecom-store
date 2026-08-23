from pydantic import BaseModel, EmailStr, Field, model_validator


class CheckoutPayload(BaseModel):
    customer_name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    product_id: str
    quantity: int = Field(ge=1, le=5)
    total_cents: int | None = Field(default=None, gt=0)
    amount_cents: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def require_amount(self):
        if self.total_cents is None and self.amount_cents is None:
            raise ValueError("total_cents or amount_cents is required")
        return self


def normalize(payload: dict) -> dict:
    normalized = CheckoutPayload.model_validate(payload).model_dump()
    normalized["total_cents"] = normalized["total_cents"] or normalized["amount_cents"]
    normalized.pop("amount_cents", None)
    return normalized

