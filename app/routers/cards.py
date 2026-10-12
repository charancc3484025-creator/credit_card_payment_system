from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import Card, CardStatus, User
from app.schemas.card import BillPaymentRequest, CardCreate, CardOut, CardResponse, CardUpdate
from app.schemas.common import MessageResponse, Page, PageParams, paginate
from app.schemas.transaction import TransactionOut
from app.services import card_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/cards", tags=["Cards"])


@router.get("", response_model=Page[CardOut])
def list_cards(
    status_filter: Optional[str] = Query(None, alias="status"),
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    for card in db.scalars(select(Card).where(Card.user_id == current_user.id, Card.status == CardStatus.ACTIVE)):
        card_service.refresh_expiry_status(db, card)

    query = db.query(Card).filter(Card.user_id == current_user.id, Card.status != CardStatus.CLOSED)
    if status_filter:
        query = query.filter(Card.status == status_filter.upper())
    return paginate(query.order_by(Card.created_at.desc(), Card.id.desc()), params, CardOut.model_validate)


@router.post("", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
def add_card(data: CardCreate, request: Request, db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    card = card_service.add_card(db, current_user, data)
    log_action(db, current_user.id, "CARD_ADDED", f"Card {card.masked_number} added", request)
    return {"message": "Card added successfully.", "card": card}


@router.get("/{card_id}", response_model=CardOut)
def get_card(card_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return card_service.get_user_card(db, current_user, card_id)


@router.patch("/{card_id}", response_model=CardResponse)
def update_card(card_id: int, data: CardUpdate, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    card = card_service.get_user_card(db, current_user, card_id)
    card = card_service.update_card(db, card, data)
    return {"message": "Card updated.", "card": card}


@router.delete("/{card_id}", response_model=MessageResponse)
def remove_card(card_id: int, request: Request, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    card = card_service.get_user_card(db, current_user, card_id)
    card_service.close_card(db, card)
    log_action(db, current_user.id, "CARD_REMOVED", f"Card {card.masked_number} closed", request)
    return {"message": "Card removed successfully."}


@router.post("/{card_id}/block", response_model=CardResponse)
def block_card(card_id: int, request: Request, db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    card = card_service.block_card(db, card_service.get_user_card(db, current_user, card_id))
    log_action(db, current_user.id, "CARD_BLOCKED", f"Card {card.masked_number} blocked by owner", request)
    return {"message": "Card blocked. Contact admin to unblock.", "card": card}


@router.post("/{card_id}/set-default", response_model=CardResponse)
def set_default(card_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    card = card_service.set_default_card(db, card_service.get_user_card(db, current_user, card_id))
    return {"message": "Default card updated.", "card": card}


@router.post("/{card_id}/pay-bill")
def pay_bill(card_id: int, data: BillPaymentRequest, request: Request, db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    card, txn = card_service.pay_card_bill(db, current_user, card_id, data.amount)
    log_action(db, current_user.id, "BILL_PAID", f"{txn.amount} paid on {card.masked_number}", request)
    return {
        "success": True,
        "message": "Bill payment successful.",
        "card": CardOut.model_validate(card),
        "transaction": TransactionOut.from_model(txn),
    }
