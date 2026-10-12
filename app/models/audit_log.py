from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BigIntPK
from app.core.utils import utc_now


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    ip_address: Mapped[Optional[str]] = mapped_column(String(39), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="fastapi")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    user_id: Mapped[Optional[int]] = mapped_column(BigIntPK, ForeignKey("users.id"), nullable=True, index=True)

    user = relationship("User")
