from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessError
from app.core.utils import generate_reference, utc_now
from app.core.validators import validate_cvv
from app.models import Card, CardStatus, Payment, PaymentStatus, Transaction, TransactionStatus, TransactionType, User
from app.schemas.payment import PaymentCreate
from app.services.card_service import get_user_card
from app.services.fraud_service import evaluate_payment


def _record_failed_payment(db: Session, user: User, card: Card, data: PaymentCreate, reason: str,
                           risk_score: int | None, idempotency_key: str | None) -> Payment:
    payment = Payment(
        user_id=user.id,
        card_id=card.id,
        merchant_name=data.merchant_name,
        amount=data.amount,
        currency=data.currency,
        description=data.description,
        status=PaymentStatus.FAILED,
        reference_id=generate_reference("PAY"),
        idempotency_key=idempotency_key,
        failure_reason=reason[:255],
        risk_score=risk_score,
        processed_by="fastapi",
    )
    db.add(payment)
    db.flush()
    db.add(Transaction(
        user_id=user.id,
        card_id=card.id,
        payment_id=payment.id,
        transaction_type=TransactionType.PURCHASE,
        amount=data.amount,
        available_credit_after=card.available_credit,
        status=TransactionStatus.FAILED,
        reference_id=generate_reference("TXN"),
        description=f"Failed: {reason}"[:255],
    ))
    db.commit()
    db.refresh(payment)
    return payment


def process_payment(db: Session, user: User, data: PaymentCreate, idempotency_key: str | None = None) -> tuple[Payment, bool]:
    if idempotency_key:
        existing = db.scalar(select(Payment).where(Payment.user_id == user.id, Payment.idempotency_key == idempotency_key))
        if existing:
            return existing, False

    card = get_user_card(db, user, data.card_id)
    if card.status != CardStatus.ACTIVE:
        raise BusinessError(f"Card is {card.status.lower()}. Payment not allowed.")
    try:
        validate_cvv(data.cvv, card.card_brand)
    except ValueError as exc:
        raise BusinessError(str(exc), errors={"cvv": [str(exc)]})

    fraud = evaluate_payment(db, user.id, card.id, data.amount, data.merchant_name)
    if not fraud["approved"]:
        reason = "Declined by fraud check: " + ", ".join(fraud["reasons"])
        return _record_failed_payment(db, user, card, data, reason, fraud["risk_score"], idempotency_key), True

    try:
        card = get_user_card(db, user, card.id, lock=True)
        if Decimal(card.available_credit) < data.amount:
            db.rollback()
            return _record_failed_payment(db, user, card, data, "Insufficient available credit",
                                          fraud["risk_score"], idempotency_key), True

        card.available_credit = Decimal(card.available_credit) - data.amount
        payment = Payment(
            user_id=user.id,
            card_id=card.id,
            merchant_name=data.merchant_name,
            amount=data.amount,
            currency=data.currency,
            description=data.description,
            status=PaymentStatus.SUCCESS,
            reference_id=generate_reference("PAY"),
            idempotency_key=idempotency_key,
            risk_score=fraud["risk_score"],
            processed_by="fastapi",
        )
        db.add(payment)
        db.flush()
        db.add(Transaction(
            user_id=user.id,
            card_id=card.id,
            payment_id=payment.id,
            transaction_type=TransactionType.PURCHASE,
            amount=data.amount,
            available_credit_after=card.available_credit,
            status=TransactionStatus.SUCCESS,
            reference_id=generate_reference("TXN"),
            description=f"Payment to {data.merchant_name}"[:255],
        ))
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Payment).where(Payment.user_id == user.id, Payment.idempotency_key == idempotency_key))
        if existing:
            return existing, False
        raise
    except Exception:
        db.rollback()
        raise

    db.refresh(payment)
    return payment, True


def refund_payment(db: Session, payment_id: int, reason: str = "") -> tuple[Payment, Transaction]:
    try:
        payment = db.scalar(
            select(Payment).where(Payment.id == payment_id).with_for_update().execution_options(populate_existing=True)
        )
        if payment is None:
            raise BusinessError("Payment not found.", status_code=404)
        if payment.status != PaymentStatus.SUCCESS:
            raise BusinessError(f"Only successful payments can be refunded (current status: {payment.status}).")

        card = db.scalar(
            select(Card).where(Card.id == payment.card_id).with_for_update().execution_options(populate_existing=True)
        )
        card.available_credit = Decimal(card.available_credit) + Decimal(payment.amount)

        payment.status = PaymentStatus.REFUNDED
        payment.refunded_at = utc_now()

        txn = Transaction(
            user_id=payment.user_id,
            card_id=card.id,
            payment_id=payment.id,
            transaction_type=TransactionType.REFUND,
            amount=payment.amount,
            available_credit_after=card.available_credit,
            status=TransactionStatus.SUCCESS,
            reference_id=generate_reference("RFD"),
            description=f"Refund for {payment.reference_id}. {reason}".strip()[:255],
        )
        db.add(txn)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(payment)
    db.refresh(txn)
    return payment, txn
