import base64
import hashlib
import hmac
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings

ALGORITHM_NAME = "pbkdf2_sha256"
SALT_CHARS = string.ascii_letters + string.digits


def _pbkdf2(password: str, salt: str, iterations: int) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    return base64.b64encode(digest).decode("ascii").strip()


def hash_password(password: str) -> str:
    salt = "".join(secrets.choice(SALT_CHARS) for _ in range(22))
    iterations = settings.PASSWORD_HASH_ITERATIONS
    return f"{ALGORITHM_NAME}${iterations}${salt}${_pbkdf2(password, salt, iterations)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, stored_hash = encoded.split("$", 3)
    except (ValueError, AttributeError):
        return False
    if algorithm != ALGORITHM_NAME:
        return False
    new_hash = _pbkdf2(password, salt, int(iterations))
    return hmac.compare_digest(new_hash, stored_hash)


class TokenError(Exception):
    pass


def _create_token(user_id: int, token_type: str, lifetime: timedelta, extra: dict | None = None) -> tuple[str, dict]:
    now = datetime.now(timezone.utc)
    payload = {
        "token_type": token_type,
        "exp": int((now + lifetime).timestamp()),
        "iat": int(now.timestamp()),
        "jti": uuid.uuid4().hex,
        "user_id": str(user_id),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, payload


def create_access_token(user_id: int, role: str) -> str:
    token, _ = _create_token(
        user_id, "access", timedelta(minutes=settings.JWT_ACCESS_MINUTES), {"role": role}
    )
    return token


def create_refresh_token(user_id: int, role: str) -> tuple[str, dict]:
    return _create_token(user_id, "refresh", timedelta(days=settings.JWT_REFRESH_DAYS), {"role": role})


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenError("Token has expired.")
    except jwt.InvalidTokenError:
        raise TokenError("Token is invalid.")

    if payload.get("token_type") != expected_type:
        raise TokenError(f"Expected a {expected_type} token.")
    if not payload.get("user_id") or not payload.get("jti"):
        raise TokenError("Token is missing required claims.")
    return payload
