from pydantic import BaseModel, EmailStr, Field


EXPECTED_FIELD = "total_cents"


class CheckoutPayload(BaseModel):
    customer_name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    product_id: str
    quantity: int = Field(ge=1, le=5)
    total_cents: int = Field(gt=0)


def normalize(payload: dict) -> dict:
    return CheckoutPayload.model_validate(payload).model_dump()
