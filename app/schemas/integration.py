from decimal import Decimal

from pydantic import BaseModel, Field


class FraudCheckRequest(BaseModel):
    user_id: int
    card_id: int
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    merchant_name: str = Field(min_length=1, max_length=150)


class FraudCheckResponse(BaseModel):
    approved: bool
    risk_score: int
    reasons: list[str]


class HealthResponse(BaseModel):
    service: str
    status: str
    database: bool
