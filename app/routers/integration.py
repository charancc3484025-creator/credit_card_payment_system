from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import verify_internal_api_key
from app.schemas.integration import FraudCheckRequest, FraudCheckResponse, HealthResponse
from app.services.fraud_service import evaluate_payment

router = APIRouter(prefix="/integration", tags=["Django Integration"], dependencies=[Depends(verify_internal_api_key)])


@router.post("/fraud-check", response_model=FraudCheckResponse)
def fraud_check(data: FraudCheckRequest, db: Session = Depends(get_db)):
    return evaluate_payment(db, data.user_id, data.card_id, data.amount, data.merchant_name)


@router.get("/health", response_model=HealthResponse)
def integration_health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"service": "fastapi", "status": "ok" if db_ok else "error", "database": db_ok}
