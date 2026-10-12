from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import Transaction, TransactionStatus, TransactionType, User
from app.schemas.common import Page, PageParams
from app.schemas.transaction import TransactionOut, TransactionSummary
from app.services.transaction_service import apply_transaction_filters

router = APIRouter(prefix="/transactions", tags=["Transactions"])


class TransactionFilters:
    def __init__(
        self,
        type: Optional[str] = Query(None, description="PURCHASE / REFUND / BILL_PAYMENT"),
        status: Optional[str] = Query(None, description="SUCCESS / FAILED"),
        card_id: Optional[int] = None,
        from_date: Optional[date] = Query(None, description="YYYY-MM-DD"),
        to_date: Optional[date] = Query(None, description="YYYY-MM-DD"),
        min_amount: Optional[Decimal] = None,
        max_amount: Optional[Decimal] = None,
        search: Optional[str] = Query(None, description="Search by reference id"),
    ):
        self.values = {
            "txn_type": type, "status": status, "card_id": card_id, "from_date": from_date,
            "to_date": to_date, "min_amount": min_amount, "max_amount": max_amount, "search": search,
        }


@router.get("", response_model=Page[TransactionOut])
def list_transactions(
    filters: TransactionFilters = Depends(),
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = apply_transaction_filters(select(Transaction).where(Transaction.user_id == current_user.id), **filters.values)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(Transaction.created_at.desc(), Transaction.id.desc()).offset(params.offset).limit(params.page_size)
    ).all()
    return {
        "count": total,
        "page": params.page,
        "page_size": params.page_size,
        "total_pages": (total + params.page_size - 1) // params.page_size,
        "results": [TransactionOut.from_model(txn) for txn in rows],
    }


@router.get("/summary", response_model=TransactionSummary)
def transaction_summary(
    filters: TransactionFilters = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base = apply_transaction_filters(select(Transaction).where(Transaction.user_id == current_user.id), **filters.values)
    sub = base.subquery()

    def total(txn_type):
        value = db.scalar(
            select(func.coalesce(func.sum(sub.c.amount), 0)).where(
                sub.c.transaction_type == txn_type, sub.c.status == TransactionStatus.SUCCESS
            )
        )
        return Decimal(value).quantize(Decimal("0.01"))

    count_rows = db.execute(select(sub.c.transaction_type, func.count()).group_by(sub.c.transaction_type)).all()

    return {
        "total_transactions": db.scalar(select(func.count()).select_from(sub)),
        "failed_transactions": db.scalar(select(func.count()).select_from(sub).where(sub.c.status == TransactionStatus.FAILED)),
        "total_spent": total(TransactionType.PURCHASE),
        "total_refunded": total(TransactionType.REFUND),
        "total_bill_paid": total(TransactionType.BILL_PAYMENT),
        "count_by_type": {row[0]: row[1] for row in count_rows},
    }


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    txn = db.scalar(select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == current_user.id))
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return TransactionOut.from_model(txn)
