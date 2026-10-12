from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BigIntPK
from app.core.utils import utc_now


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    password: Mapped[str] = mapped_column(String(128))
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    first_name: Mapped[str] = mapped_column(String(150), default="")
    last_name: Mapped[str] = mapped_column(String(150), default="")
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    date_joined: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    phone_number: Mapped[str] = mapped_column(String(15), default="")
    role: Mapped[str] = mapped_column(String(10), default="CUSTOMER")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    cards = relationship("Card", back_populates="user")

    ROLE_CUSTOMER = "CUSTOMER"
    ROLE_ADMIN = "ADMIN"

    @property
    def is_admin(self) -> bool:
        return self.role == self.ROLE_ADMIN or self.is_superuser

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()
