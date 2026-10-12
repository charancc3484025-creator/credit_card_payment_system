from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BigIntPK
from app.core.utils import utc_now


class PaymentStatus:
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    merchant_name: Mapped[str] = mapped_column(String(150))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    description: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(10), default=PaymentStatus.PENDING)
    reference_id: Mapped[str] = mapped_column(String(30), unique=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    failure_reason: Mapped[str] = mapped_column(String(255), default="")
    risk_score: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    processed_by: Mapped[str] = mapped_column(String(20), default="fastapi")
    refunded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    card_id: Mapped[int] = mapped_column(BigIntPK, ForeignKey("cards.id"), index=True)
    user_id: Mapped[int] = mapped_column(BigIntPK, ForeignKey("users.id"), index=True)

    card = relationship("Card")
    user = relationship("User")
