from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BigIntPK
from app.core.utils import utc_now


class OutstandingToken(Base):
    __tablename__ = "token_blacklist_outstandingtoken"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    user_id: Mapped[Optional[int]] = mapped_column(BigIntPK, ForeignKey("users.id"), nullable=True, index=True)
    jti: Mapped[str] = mapped_column(String(255), unique=True)

    blacklisted = relationship("BlacklistedToken", back_populates="token", uselist=False)


class BlacklistedToken(Base):
    __tablename__ = "token_blacklist_blacklistedtoken"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    blacklisted_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    token_id: Mapped[int] = mapped_column(BigIntPK, ForeignKey("token_blacklist_outstandingtoken.id"), unique=True)

    token = relationship("OutstandingToken", back_populates="blacklisted")
