import hmac

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import RateLimiter
from app.core.security import TokenError, decode_token
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)

login_rate_limiter = RateLimiter(settings.LOGIN_RATE_LIMIT_PER_MINUTE, scope="login")
payment_rate_limiter = RateLimiter(settings.PAYMENT_RATE_LIMIT_PER_MINUTE, scope="payment")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials were not provided or are invalid.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except TokenError as exc:
        unauthorized.detail = str(exc)
        raise unauthorized

    user = db.get(User, int(payload["user_id"]))
    if user is None:
        unauthorized.detail = "User not found."
        raise unauthorized
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your account has been blocked.")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin users can perform this action.")
    return current_user


def verify_internal_api_key(x_internal_api_key: str | None = Header(default=None)) -> None:
    if not settings.INTERNAL_API_KEY or not x_internal_api_key or not hmac.compare_digest(
        x_internal_api_key, settings.INTERNAL_API_KEY
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal API key.")
