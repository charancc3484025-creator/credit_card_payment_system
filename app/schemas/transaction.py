from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from app.schemas.common import ORMModel, UTCDateTime


class TransactionOut(ORMModel):
    id: int
    reference_id: str
    transaction_type: str
    amount: Decimal
    available_credit_after: Decimal
    status: str
    description: str
    card_id: int
    card_masked_number: str
    payment_id: Optional[int] = None
    payment_reference: Optional[str] = None
    created_at: UTCDateTime

    @classmethod
    def from_model(cls, txn):
        return cls.model_validate({
            **{field: getattr(txn, field) for field in (
                "id", "reference_id", "transaction_type", "amount", "available_credit_after",
                "status", "description", "card_id", "payment_id", "created_at",
            )},
            "card_masked_number": txn.card.masked_number,
            "payment_reference": txn.payment.reference_id if txn.payment else None,
        })


class AdminTransactionOut(TransactionOut):
    user_id: int
    user_email: str

    @classmethod
    def from_model(cls, txn):
        base = TransactionOut.from_model(txn).model_dump()
        return cls.model_validate({**base, "user_id": txn.user_id, "user_email": txn.user.email})


class TransactionSummary(BaseModel):
    total_transactions: int
    failed_transactions: int
    total_spent: Decimal
    total_refunded: Decimal
    total_bill_paid: Decimal
    count_by_type: dict[str, int]
