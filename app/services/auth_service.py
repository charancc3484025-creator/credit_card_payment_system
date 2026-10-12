from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessError
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.utils import utc_now
from app.models import BlacklistedToken, OutstandingToken, User
from app.schemas.user import RegisterRequest


def issue_tokens(db: Session, user: User) -> dict:
    refresh, payload = create_refresh_token(user.id, user.role)
    db.add(OutstandingToken(
        user_id=user.id,
        jti=payload["jti"],
        token=refresh,
        created_at=utc_now(),
        expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc).replace(tzinfo=None),
    ))
    db.commit()
    return {"access": create_access_token(user.id, user.role), "refresh": refresh}


def register_user(db: Session, data: RegisterRequest) -> User:
    if db.scalar(select(User).where(User.email == data.email)):
        raise BusinessError("A user with this email already exists.", errors={"email": ["Already registered."]})

    user = User(
        email=data.email,
        first_name=data.first_name,
        last_name=data.last_name,
        phone_number=data.phone_number,
        password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BusinessError("A user with this email already exists.")
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or not verify_password(password, user.password):
        raise BusinessError("Invalid email or password.")
    if not user.is_active:
        raise BusinessError("Your account has been blocked. Contact support.", status_code=403)
    user.last_login = utc_now()
    db.commit()
    return user


def _blacklist(db: Session, payload: dict, raw_token: str) -> None:
    outstanding = db.scalar(select(OutstandingToken).where(OutstandingToken.jti == payload["jti"]))
    if outstanding is None:
        outstanding = OutstandingToken(
            user_id=int(payload["user_id"]),
            jti=payload["jti"],
            token=raw_token,
            created_at=utc_now(),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc).replace(tzinfo=None),
        )
        db.add(outstanding)
        db.flush()
    if outstanding.blacklisted is None:
        db.add(BlacklistedToken(token_id=outstanding.id, blacklisted_at=utc_now()))


def _is_blacklisted(db: Session, jti: str) -> bool:
    return db.scalar(
        select(BlacklistedToken.id).join(OutstandingToken).where(OutstandingToken.jti == jti)
    ) is not None


def refresh_tokens(db: Session, refresh_token: str) -> dict:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise BusinessError(str(exc), status_code=401)

    if _is_blacklisted(db, payload["jti"]):
        raise BusinessError("Token is blacklisted.", status_code=401)

    user = db.get(User, int(payload["user_id"]))
    if user is None or not user.is_active:
        raise BusinessError("User not found or blocked.", status_code=401)

    _blacklist(db, payload, refresh_token)
    db.commit()
    return issue_tokens(db, user)


def logout(db: Session, user: User, refresh_token: str) -> None:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except TokenError:
        raise BusinessError("Invalid or expired refresh token.")
    if str(payload["user_id"]) != str(user.id):
        raise BusinessError("Token does not belong to this user.")
    _blacklist(db, payload, refresh_token)
    db.commit()


def change_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    if not verify_password(old_password, user.password):
        raise BusinessError("Old password is incorrect.", errors={"old_password": ["Incorrect password."]})
    user.password = hash_password(new_password)
    db.commit()
