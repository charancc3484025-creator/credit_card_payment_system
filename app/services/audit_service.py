import logging

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog

logger = logging.getLogger("ccps")


def get_client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def log_action(db: Session, user_id: int | None, action: str, description: str = "", request: Request | None = None):
    try:
        db.add(AuditLog(
            user_id=user_id,
            action=action,
            description=description,
            ip_address=get_client_ip(request),
            source="fastapi",
        ))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not write audit log for action %s", action)
