from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BigIntPK
from app.core.utils import utc_now


class TransactionType:
    PURCHASE = "PURCHASE"
    REFUND = "REFUND"
    BILL_PAYMENT = "BILL_PAYMENT"


class TransactionStatus:
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    transaction_type: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    available_credit_after: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(10))
    reference_id: Mapped[str] = mapped_column(String(30), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    card_id: Mapped[int] = mapped_column(BigIntPK, ForeignKey("cards.id"), index=True)
    payment_id: Mapped[Optional[int]] = mapped_column(BigIntPK, ForeignKey("payments.id"), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(BigIntPK, ForeignKey("users.id"), index=True)

    card = relationship("Card")
    payment = relationship("Payment")
    user = relationship("User")
