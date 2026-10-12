from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BigIntPK
from app.core.encryption import mask_card_number
from app.core.utils import utc_now


class CardStatus:
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    EXPIRED = "EXPIRED"
    CLOSED = "CLOSED"


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    card_holder_name: Mapped[str] = mapped_column(String(100))
    card_number_encrypted: Mapped[str] = mapped_column(Text)
    card_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    last_four: Mapped[str] = mapped_column(String(4))
    card_brand: Mapped[str] = mapped_column(String(20))
    expiry_month: Mapped[int] = mapped_column(SmallInteger)
    expiry_year: Mapped[int] = mapped_column(SmallInteger)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    available_credit: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(10), default=CardStatus.ACTIVE)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    user_id: Mapped[int] = mapped_column(BigIntPK, ForeignKey("users.id"), index=True)

    user = relationship("User", back_populates="cards")

    @property
    def masked_number(self) -> str:
        return mask_card_number(self.last_four)

    @property
    def outstanding_amount(self) -> Decimal:
        return (Decimal(self.credit_limit) - Decimal(self.available_credit)).quantize(Decimal("0.01"))

    @property
    def is_expired(self) -> bool:
        today = date.today()
        return (self.expiry_year, self.expiry_month) < (today.year, today.month)
