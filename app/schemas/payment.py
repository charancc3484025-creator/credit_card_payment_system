from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.schemas.common import UTCDateTime
from app.schemas.transaction import TransactionOut


class PaymentCreate(BaseModel):
    card_id: int
    amount: Decimal = Field(ge=Decimal("1.00"), max_digits=12, decimal_places=2)
    merchant_name: str = Field(min_length=2, max_length=150)
    cvv: str = Field(min_length=3, max_length=4)
    currency: Literal["INR"] = "INR"
    description: str = Field(default="", max_length=255)

    @field_validator("amount")
    @classmethod
    def check_max_amount(cls, value: Decimal) -> Decimal:
        if value > settings.MAX_SINGLE_PAYMENT:
            raise ValueError(f"Single payment cannot be more than {settings.MAX_SINGLE_PAYMENT}.")
        return value

    @field_validator("merchant_name")
    @classmethod
    def strip_merchant(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Merchant name is too short.")
        return value


class PaymentOut(BaseModel):
    id: int
    reference_id: str
    card_id: int
    card_masked_number: str
    card_brand: str
    merchant_name: str
    amount: Decimal
    currency: str
    description: str
    status: str
    failure_reason: str
    risk_score: Optional[int] = None
    processed_by: str
    refunded_at: Optional[UTCDateTime] = None
    created_at: UTCDateTime
    updated_at: UTCDateTime

    @classmethod
    def from_model(cls, payment):
        return cls(
            id=payment.id,
            reference_id=payment.reference_id,
            card_id=payment.card_id,
            card_masked_number=payment.card.masked_number,
            card_brand=payment.card.card_brand,
            merchant_name=payment.merchant_name,
            amount=payment.amount,
            currency=payment.currency,
            description=payment.description,
            status=payment.status,
            failure_reason=payment.failure_reason,
            risk_score=payment.risk_score,
            processed_by=payment.processed_by,
            refunded_at=payment.refunded_at,
            created_at=payment.created_at,
            updated_at=payment.updated_at,
        )


class AdminPaymentOut(PaymentOut):
    user_id: int
    user_email: str

    @classmethod
    def from_model(cls, payment):
        base = PaymentOut.from_model(payment).model_dump()
        return cls(**base, user_id=payment.user_id, user_email=payment.user.email)


class PaymentResponse(BaseModel):
    success: bool
    message: str
    payment: PaymentOut


class RefundRequest(BaseModel):
    reason: str = Field(default="", max_length=255)


class RefundResponse(BaseModel):
    success: bool = True
    message: str
    payment: PaymentOut
    transaction: TransactionOut
