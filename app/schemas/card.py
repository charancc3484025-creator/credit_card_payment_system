from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel, UTCDateTime


class CardCreate(BaseModel):
    card_holder_name: str = Field(min_length=2, max_length=100)
    card_number: str = Field(min_length=13, max_length=23)
    expiry_month: int
    expiry_year: int
    cvv: str = Field(min_length=3, max_length=4)
    is_default: bool = False

    @field_validator("card_holder_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not all(ch.isalpha() or ch in ".'" for ch in value.replace(" ", "")):
            raise ValueError("Card holder name can contain only letters.")
        return value.upper()


class CardUpdate(BaseModel):
    card_holder_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    is_default: Optional[bool] = None

    @field_validator("card_holder_name")
    @classmethod
    def clean_name(cls, value):
        return " ".join(value.split()).upper() if value else value


class CardOut(ORMModel):
    id: int
    card_holder_name: str
    masked_number: str
    last_four: str
    card_brand: str
    expiry_month: int
    expiry_year: int
    credit_limit: Decimal
    available_credit: Decimal
    outstanding_amount: Decimal
    status: str
    is_default: bool
    created_at: UTCDateTime
    updated_at: UTCDateTime


class CardResponse(BaseModel):
    success: bool = True
    message: str
    card: CardOut


class BillPaymentRequest(BaseModel):
    amount: Decimal = Field(ge=Decimal("1.00"), max_digits=12, decimal_places=2)
