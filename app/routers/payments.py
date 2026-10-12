from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_user, payment_rate_limiter, require_admin
from app.models import Payment, PaymentStatus, User
from app.schemas.common import Page, PageParams, paginate
from app.schemas.payment import PaymentCreate, PaymentOut, PaymentResponse, RefundRequest, RefundResponse
from app.schemas.transaction import TransactionOut
from app.services import payment_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.get("", response_model=Page[PaymentOut])
def list_payments(
    status_filter: Optional[str] = Query(None, alias="status"),
    card_id: Optional[int] = None,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Payment).options(joinedload(Payment.card)).filter(Payment.user_id == current_user.id)
    if status_filter:
        query = query.filter(Payment.status == status_filter.upper())
    if card_id:
        query = query.filter(Payment.card_id == card_id)
    return paginate(query.order_by(Payment.created_at.desc(), Payment.id.desc()), params, PaymentOut.from_model)


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(payment_rate_limiter)],
    responses={402: {"description": "Payment failed (declined or insufficient credit)"}},
)
def make_payment(
    data: PaymentCreate,
    request: Request,
    response: Response,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key", max_length=64),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment, created = payment_service.process_payment(db, current_user, data, idempotency_key)

    if not created:
        response.status_code = status.HTTP_200_OK
        return {"success": payment.status == PaymentStatus.SUCCESS,
                "message": "Duplicate request - returning the original payment.",
                "payment": PaymentOut.from_model(payment)}

    if payment.status == PaymentStatus.SUCCESS:
        log_action(db, current_user.id, "PAYMENT_SUCCESS", f"{payment.reference_id} amount {payment.amount}", request)
        return {"success": True, "message": "Payment successful.", "payment": PaymentOut.from_model(payment)}

    log_action(db, current_user.id, "PAYMENT_FAILED", f"{payment.reference_id}: {payment.failure_reason}", request)
    response.status_code = status.HTTP_402_PAYMENT_REQUIRED
    return {"success": False, "message": payment.failure_reason, "payment": PaymentOut.from_model(payment)}


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.user_id == current_user.id).first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    return PaymentOut.from_model(payment)


@router.post("/{payment_id}/refund", response_model=RefundResponse)
def refund(payment_id: int, request: Request, data: RefundRequest | None = None, db: Session = Depends(get_db),
           admin: User = Depends(require_admin)):
    payment, txn = payment_service.refund_payment(db, payment_id, data.reason if data else "")
    log_action(db, admin.id, "PAYMENT_REFUNDED", f"{payment.reference_id} refunded by admin", request)
    return {
        "message": "Payment refunded successfully.",
        "payment": PaymentOut.from_model(payment),
        "transaction": TransactionOut.from_model(txn),
    }
