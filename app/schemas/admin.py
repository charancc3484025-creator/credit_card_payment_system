from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.card import CardOut
from app.schemas.common import ORMModel, UTCDateTime


class AdminUserOut(ORMModel):
    id: int
    email: str
    first_name: str
    last_name: str
    phone_number: str
    role: str
    is_active: bool
    date_joined: UTCDateTime
    last_login: Optional[UTCDateTime] = None
    total_cards: int = 0


class AdminCardOut(CardOut):
    user_id: int
    user_email: str

    @classmethod
    def from_model(cls, card):
        base = CardOut.model_validate(card).model_dump()
        return cls(**base, user_id=card.user_id, user_email=card.user.email)


class AdminUserDetail(AdminUserOut):
    cards: list[AdminCardOut]
    total_spent: Decimal


class AdminUserResponse(BaseModel):
    success: bool = True
    message: str
    user: AdminUserOut


class AdminCardResponse(BaseModel):
    success: bool = True
    message: str
    card: AdminCardOut


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserRoleUpdate(BaseModel):
    role: Literal["CUSTOMER", "ADMIN"]


class CardStatusUpdate(BaseModel):
    status: Literal["ACTIVE", "BLOCKED"]


class CreditLimitUpdate(BaseModel):
    credit_limit: Decimal = Field(ge=Decimal("1000.00"), max_digits=12, decimal_places=2)


class AuditLogOut(ORMModel):
    id: int
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    action: str
    description: str
    ip_address: Optional[str] = None
    source: str
    created_at: UTCDateTime

    @classmethod
    def from_model(cls, log):
        return cls(
            id=log.id, user_id=log.user_id, user_email=log.user.email if log.user else None,
            action=log.action, description=log.description, ip_address=log.ip_address,
            source=log.source, created_at=log.created_at,
        )


class DashboardUsers(BaseModel):
    total: int
    active: int
    blocked: int
    admins: int


class DashboardCards(BaseModel):
    total: int
    active: int
    blocked: int
    total_credit_limit: Decimal


class DashboardPayments(BaseModel):
    total: int
    success: int
    failed: int
    refunded: int
    total_amount: Decimal
    today_amount: Decimal
    last_30_days_amount: Decimal


class DashboardTransactions(BaseModel):
    total: int
    by_type: dict[str, int]


class DashboardOut(BaseModel):
    users: DashboardUsers
    cards: DashboardCards
    payments: DashboardPayments
    transactions: DashboardTransactions
