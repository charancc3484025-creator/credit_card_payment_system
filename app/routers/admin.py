from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.utils import utc_now
from app.models import AuditLog, Card, CardStatus, Payment, PaymentStatus, Transaction, User
from app.routers.transactions import TransactionFilters
from app.schemas.admin import (
    AdminCardOut,
    AdminCardResponse,
    AdminUserDetail,
    AdminUserOut,
    AdminUserResponse,
    AuditLogOut,
    CardStatusUpdate,
    CreditLimitUpdate,
    DashboardOut,
    UserRoleUpdate,
    UserStatusUpdate,
)
from app.schemas.common import Page, PageParams, paginate
from app.schemas.payment import AdminPaymentOut
from app.schemas.transaction import AdminTransactionOut
from app.services.audit_service import log_action
from app.services.transaction_service import LOCAL_TZ, apply_transaction_filters

router = APIRouter(prefix="/admin", tags=["Admin"])

ZERO = Decimal("0.00")


def _open_card_count(db: Session, user_id: int) -> int:
    return db.scalar(
        select(func.count(Card.id)).where(Card.user_id == user_id, Card.status != CardStatus.CLOSED)
    ) or 0


def _admin_user(db: Session, user: User) -> AdminUserOut:
    data = AdminUserOut.model_validate(user)
    data.total_cards = _open_card_count(db, user.id)
    return data


def _sum(db: Session, query) -> Decimal:
    return Decimal(db.scalar(query) or 0).quantize(Decimal("0.01"))


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    local_midnight = datetime.now(LOCAL_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    today_start = local_midnight.astimezone(timezone.utc).replace(tzinfo=None)
    last_30_days = utc_now() - timedelta(days=30)

    def count(model, *conditions):
        return db.scalar(select(func.count(model.id)).where(*conditions)) or 0

    success = Payment.status == PaymentStatus.SUCCESS
    type_counts = db.execute(select(Transaction.transaction_type, func.count()).group_by(Transaction.transaction_type)).all()

    return {
        "users": {
            "total": count(User),
            "active": count(User, User.is_active.is_(True)),
            "blocked": count(User, User.is_active.is_(False)),
            "admins": count(User, User.role == User.ROLE_ADMIN),
        },
        "cards": {
            "total": count(Card, Card.status != CardStatus.CLOSED),
            "active": count(Card, Card.status == CardStatus.ACTIVE),
            "blocked": count(Card, Card.status == CardStatus.BLOCKED),
            "total_credit_limit": _sum(db, select(func.sum(Card.credit_limit)).where(Card.status != CardStatus.CLOSED)),
        },
        "payments": {
            "total": count(Payment),
            "success": count(Payment, success),
            "failed": count(Payment, Payment.status == PaymentStatus.FAILED),
            "refunded": count(Payment, Payment.status == PaymentStatus.REFUNDED),
            "total_amount": _sum(db, select(func.sum(Payment.amount)).where(success)),
            "today_amount": _sum(db, select(func.sum(Payment.amount)).where(success, Payment.created_at >= today_start)),
            "last_30_days_amount": _sum(db, select(func.sum(Payment.amount)).where(success, Payment.created_at >= last_30_days)),
        },
        "transactions": {
            "total": count(Transaction),
            "by_type": {row[0]: row[1] for row in type_counts},
        },
    }


@router.get("/users", response_model=Page[AdminUserOut])
def list_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = db.query(User)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(User.email.ilike(term), User.first_name.ilike(term), User.last_name.ilike(term)))
    if role:
        query = query.filter(User.role == role.upper())
    if is_active is not None:
        query = query.filter(User.is_active.is_(is_active))
    return paginate(query.order_by(User.date_joined.desc(), User.id.desc()), params, lambda u: _admin_user(db, u))


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def user_detail(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = _get_user_or_404(db, user_id)
    cards = db.scalars(select(Card).where(Card.user_id == user.id, Card.status != CardStatus.CLOSED)).all()
    total_spent = _sum(db, select(func.sum(Payment.amount)).where(
        Payment.user_id == user.id, Payment.status == PaymentStatus.SUCCESS
    ))
    return AdminUserDetail(
        **_admin_user(db, user).model_dump(),
        cards=[AdminCardOut.from_model(card) for card in cards],
        total_spent=total_spent,
    )


@router.post("/users/{user_id}/status", response_model=AdminUserResponse)
def change_user_status(user_id: int, data: UserStatusUpdate, request: Request, db: Session = Depends(get_db),
                       admin: User = Depends(require_admin)):
    user = _get_user_or_404(db, user_id)
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot change your own status.")
    user.is_active = data.is_active
    db.commit()
    log_action(db, admin.id, "USER_UNBLOCKED" if user.is_active else "USER_BLOCKED", f"User {user.email}", request)
    return {"message": f"User {'unblocked' if user.is_active else 'blocked'}.", "user": _admin_user(db, user)}


@router.post("/users/{user_id}/role", response_model=AdminUserResponse)
def change_user_role(user_id: int, data: UserRoleUpdate, request: Request, db: Session = Depends(get_db),
                     admin: User = Depends(require_admin)):
    user = _get_user_or_404(db, user_id)
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot change your own role.")
    user.role = data.role
    db.commit()
    log_action(db, admin.id, "USER_ROLE_CHANGED", f"User {user.email} -> {user.role}", request)
    return {"message": "Role updated.", "user": _admin_user(db, user)}


@router.get("/cards", response_model=Page[AdminCardOut])
def list_all_cards(
    status: Optional[str] = None,
    user_id: Optional[int] = None,
    brand: Optional[str] = None,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = db.query(Card)
    if status:
        query = query.filter(Card.status == status.upper())
    if user_id:
        query = query.filter(Card.user_id == user_id)
    if brand:
        query = query.filter(Card.card_brand == brand.upper())
    return paginate(query.order_by(Card.created_at.desc(), Card.id.desc()), params, AdminCardOut.from_model)


def _get_card_or_404(db: Session, card_id: int, lock: bool = False) -> Card:
    query = select(Card).where(Card.id == card_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    card = db.scalar(query)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found.")
    return card


@router.post("/cards/{card_id}/status", response_model=AdminCardResponse)
def change_card_status(card_id: int, data: CardStatusUpdate, request: Request, db: Session = Depends(get_db),
                       admin: User = Depends(require_admin)):
    card = _get_card_or_404(db, card_id)
    if card.status in (CardStatus.CLOSED, CardStatus.EXPIRED):
        raise HTTPException(status_code=400, detail=f"Card is {card.status.lower()} and cannot be changed.")
    card.status = data.status
    db.commit()
    log_action(db, admin.id, f"ADMIN_CARD_{data.status}", f"Card {card.id} of {card.user.email}", request)
    return {"message": f"Card status changed to {data.status}.", "card": AdminCardOut.from_model(card)}


@router.post("/cards/{card_id}/credit-limit", response_model=AdminCardResponse)
def change_credit_limit(card_id: int, data: CreditLimitUpdate, request: Request, db: Session = Depends(get_db),
                        admin: User = Depends(require_admin)):
    try:
        card = _get_card_or_404(db, card_id, lock=True)
        used = Decimal(card.credit_limit) - Decimal(card.available_credit)
        if data.credit_limit < used:
            raise HTTPException(status_code=400, detail=f"New limit cannot be less than the used amount {used}.")
        old_limit = card.credit_limit
        card.credit_limit = data.credit_limit
        card.available_credit = data.credit_limit - used
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(card)
    log_action(db, admin.id, "CREDIT_LIMIT_CHANGED", f"Card {card.id}: {old_limit} -> {data.credit_limit}", request)
    return {"message": "Credit limit updated.", "card": AdminCardOut.from_model(card)}


@router.get("/payments", response_model=Page[AdminPaymentOut])
def list_all_payments(
    status: Optional[str] = None,
    user_id: Optional[int] = None,
    search: Optional[str] = None,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = db.query(Payment)
    if status:
        query = query.filter(Payment.status == status.upper())
    if user_id:
        query = query.filter(Payment.user_id == user_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(Payment.reference_id.ilike(term), Payment.merchant_name.ilike(term)))
    return paginate(query.order_by(Payment.created_at.desc(), Payment.id.desc()), params, AdminPaymentOut.from_model)


@router.get("/payments/{payment_id}", response_model=AdminPaymentOut)
def payment_detail(payment_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    return AdminPaymentOut.from_model(payment)


@router.get("/transactions", response_model=Page[AdminTransactionOut])
def list_all_transactions(
    user_id: Optional[int] = None,
    filters: TransactionFilters = Depends(),
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = select(Transaction)
    if user_id:
        query = query.where(Transaction.user_id == user_id)
    query = apply_transaction_filters(query, **filters.values)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(Transaction.created_at.desc(), Transaction.id.desc()).offset(params.offset).limit(params.page_size)
    ).all()
    return {
        "count": total,
        "page": params.page,
        "page_size": params.page_size,
        "total_pages": (total + params.page_size - 1) // params.page_size,
        "results": [AdminTransactionOut.from_model(txn) for txn in rows],
    }


@router.get("/audit-logs", response_model=Page[AuditLogOut])
def audit_logs(
    action: Optional[str] = Query(None),
    user_id: Optional[int] = None,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = db.query(AuditLog)
    if action:
        query = query.filter(func.upper(AuditLog.action) == action.upper())
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    return paginate(query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()), params, AuditLogOut.from_model)
