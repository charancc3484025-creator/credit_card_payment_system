from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption import card_fingerprint, encrypt_card_number
from app.core.exceptions import BusinessError
from app.core.utils import generate_reference
from app.core.validators import detect_card_brand, validate_card_number, validate_cvv, validate_expiry
from app.models import Card, CardStatus, Transaction, TransactionStatus, TransactionType, User
from app.schemas.card import CardCreate, CardUpdate


def refresh_expiry_status(db: Session, card: Card) -> Card:
    if card.is_expired and card.status == CardStatus.ACTIVE:
        card.status = CardStatus.EXPIRED
        db.commit()
    return card


def get_user_card(db: Session, user: User, card_id: int, lock: bool = False) -> Card:
    query = select(Card).where(Card.id == card_id, Card.user_id == user.id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    card = db.scalar(query)
    if card is None:
        raise BusinessError("Card not found.", status_code=404)
    return card if lock else refresh_expiry_status(db, card)


def _clear_default(db: Session, user_id: int, except_id: int | None = None):
    query = update(Card).where(Card.user_id == user_id, Card.is_default.is_(True))
    if except_id:
        query = query.where(Card.id != except_id)
    db.execute(query.values(is_default=False))


def add_card(db: Session, user: User, data: CardCreate) -> Card:
    try:
        number = validate_card_number(data.card_number)
        validate_expiry(data.expiry_month, data.expiry_year)
        brand = detect_card_brand(number)
        validate_cvv(data.cvv, brand)
    except ValueError as exc:
        raise BusinessError(str(exc), errors={"card": [str(exc)]})

    fingerprint = card_fingerprint(number)
    existing = db.scalar(select(Card).where(Card.user_id == user.id, Card.card_fingerprint == fingerprint))
    if existing and existing.status != CardStatus.CLOSED:
        raise BusinessError("This card is already added to your account.")

    has_open_cards = db.scalar(
        select(Card.id).where(Card.user_id == user.id, Card.status != CardStatus.CLOSED).limit(1)
    ) is not None
    make_default = data.is_default or not has_open_cards
    if make_default:
        _clear_default(db, user.id)

    card = existing or Card(user_id=user.id, card_fingerprint=fingerprint)
    card.card_holder_name = data.card_holder_name
    card.card_number_encrypted = encrypt_card_number(number)
    card.last_four = number[-4:]
    card.card_brand = brand
    card.expiry_month = data.expiry_month
    card.expiry_year = data.expiry_year
    card.credit_limit = settings.DEFAULT_CREDIT_LIMIT
    card.available_credit = settings.DEFAULT_CREDIT_LIMIT
    card.status = CardStatus.ACTIVE
    card.is_default = make_default
    if existing is None:
        db.add(card)
    db.commit()
    db.refresh(card)
    return card


def update_card(db: Session, card: Card, data: CardUpdate) -> Card:
    if card.status == CardStatus.CLOSED:
        raise BusinessError("Closed card cannot be updated.")
    if data.card_holder_name is not None:
        card.card_holder_name = data.card_holder_name
    if data.is_default is not None:
        if data.is_default:
            _clear_default(db, card.user_id, except_id=card.id)
        card.is_default = data.is_default
    db.commit()
    db.refresh(card)
    return card


def close_card(db: Session, card: Card) -> None:
    if card.outstanding_amount > 0:
        raise BusinessError(f"Please clear the outstanding amount {card.outstanding_amount} before removing the card.")
    card.status = CardStatus.CLOSED
    card.is_default = False
    db.commit()


def block_card(db: Session, card: Card) -> Card:
    if card.status != CardStatus.ACTIVE:
        raise BusinessError(f"Card is already {card.status.lower()}.")
    card.status = CardStatus.BLOCKED
    db.commit()
    db.refresh(card)
    return card


def set_default_card(db: Session, card: Card) -> Card:
    if card.status != CardStatus.ACTIVE:
        raise BusinessError("Only active cards can be set as default.")
    _clear_default(db, card.user_id)
    card.is_default = True
    db.commit()
    db.refresh(card)
    return card


def pay_card_bill(db: Session, user: User, card_id: int, amount: Decimal) -> tuple[Card, Transaction]:
    try:
        card = get_user_card(db, user, card_id, lock=True)
        if card.status == CardStatus.CLOSED:
            raise BusinessError("This card is closed.")
        outstanding = card.outstanding_amount
        if outstanding <= 0:
            raise BusinessError("There is no outstanding amount on this card.")
        if amount > outstanding:
            raise BusinessError(f"Amount cannot be more than outstanding amount {outstanding}.")

        card.available_credit = Decimal(card.available_credit) + amount
        txn = Transaction(
            user_id=user.id,
            card_id=card.id,
            transaction_type=TransactionType.BILL_PAYMENT,
            amount=amount,
            available_credit_after=card.available_credit,
            status=TransactionStatus.SUCCESS,
            reference_id=generate_reference("BIL"),
            description="Credit card bill payment",
        )
        db.add(txn)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(card)
    db.refresh(txn)
    return card, txn
