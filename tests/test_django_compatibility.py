import time
import uuid

import jwt

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password, verify_password
from app.models import User

DJANGO_HASH = "pbkdf2_sha256$1000000$fixedsalt123$BNPA79uc+4N9KwSIsS0yADcU8dQ4QfprjVBhfTwx660="


def test_verify_django_password_hash():
    assert verify_password("Test@1234", DJANGO_HASH)
    assert not verify_password("Wrong@1234", DJANGO_HASH)


def test_our_hash_uses_django_format():
    encoded = hash_password("Test@1234")
    algorithm, iterations, salt, digest = encoded.split("$")
    assert algorithm == "pbkdf2_sha256"
    assert verify_password("Test@1234", encoded)


def test_user_created_by_django_can_login(client):
    session = SessionLocal()
    session.add(User(email="django.user@test.com", password=DJANGO_HASH, first_name="Dj", last_name="User"))
    session.commit()
    session.close()

    response = client.post("/api/v1/auth/login", json={"email": "django.user@test.com", "password": "Test@1234"})
    assert response.status_code == 200


def test_simplejwt_style_token_is_accepted(client, customer):
    now = int(time.time())
    django_token = jwt.encode(
        {"token_type": "access", "exp": now + 300, "iat": now, "jti": uuid.uuid4().hex, "user_id": str(customer.id)},
        settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )
    response = client.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {django_token}"})
    assert response.status_code == 200
    assert response.json()["id"] == customer.id


def test_token_with_wrong_secret_is_rejected(client, customer):
    now = int(time.time())
    bad = jwt.encode(
        {"token_type": "access", "exp": now + 300, "iat": now, "jti": "x", "user_id": str(customer.id)},
        "some-other-secret-key-that-is-long-enough",
        algorithm="HS256",
    )
    assert client.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {bad}"}).status_code == 401


def test_expired_token_is_rejected(client, customer):
    now = int(time.time())
    expired = jwt.encode(
        {"token_type": "access", "exp": now - 10, "iat": now - 400, "jti": "x", "user_id": str(customer.id)},
        settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )
    response = client.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    assert "expired" in response.json()["message"].lower()
