from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.utils import utc_now
from app.models import Card, CardStatus, Payment, PaymentStatus, User


def evaluate_payment(db: Session, user_id: int, card_id: int, amount: Decimal, merchant_name: str) -> dict:
    reasons: list[str] = []
    score = 0

    user = db.get(User, user_id)
    card = db.get(Card, card_id)

    if user is None or not user.is_active:
        return {"approved": False, "risk_score": 100, "reasons": ["user not found or blocked"]}
    if card is None or card.user_id != user_id:
        return {"approved": False, "risk_score": 100, "reasons": ["card does not belong to user"]}
    if card.status != CardStatus.ACTIVE:
        return {"approved": False, "risk_score": 100, "reasons": [f"card is {card.status.lower()}"]}

    window_start = utc_now() - timedelta(minutes=settings.FRAUD_WINDOW_MINUTES)
    recent_count = db.scalar(
        select(func.count(Payment.id)).where(Payment.card_id == card_id, Payment.created_at >= window_start)
    ) or 0
    if recent_count >= settings.FRAUD_MAX_PAYMENTS_IN_WINDOW:
        score += 70
        reasons.append("too many payments in short time")

    if amount >= settings.FRAUD_HIGH_AMOUNT:
        score += 50
        reasons.append("high amount")

    if card.credit_limit and amount >= Decimal(card.credit_limit) * Decimal("0.9"):
        score += 20
        reasons.append("amount close to credit limit")

    failed_recent = db.scalar(
        select(func.count(Payment.id)).where(
            Payment.card_id == card_id,
            Payment.status == PaymentStatus.FAILED,
            Payment.created_at >= window_start,
        )
    ) or 0
    if failed_recent >= 3:
        score += 30
        reasons.append("multiple failed payments recently")

    score = min(score, 100)
    return {"approved": score < settings.FRAUD_DECLINE_SCORE, "risk_score": score, "reasons": reasons}
