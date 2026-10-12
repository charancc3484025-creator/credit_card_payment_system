import os
import tempfile
from datetime import date

from cryptography.fernet import Fernet

_db_file = os.path.join(tempfile.gettempdir(), "ccps_fastapi_test.db")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_db_file}")
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-which-is-long-enough-123"
os.environ["CARD_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["INTERNAL_API_KEY"] = "test-internal-key"
os.environ["PASSWORD_HASH_ITERATIONS"] = "1000"

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.core.dependencies import login_rate_limiter, payment_rate_limiter
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import User

PASSWORD = "Strong@Pass123"
VISA_CARD = "4111111111111111"
MASTER_CARD = "5555555555554444"
AMEX_CARD = "378282246310005"


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    login_rate_limiter.reset()
    payment_rate_limiter.reset()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_user(email="customer@test.com", role="CUSTOMER", password=PASSWORD, is_active=True):
    session = SessionLocal()
    user = User(
        email=email, password=hash_password(password), first_name="Test", last_name="User",
        role=role, is_active=is_active,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    session.close()
    return user


def auth_headers(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


@pytest.fixture
def customer():
    return create_user()


@pytest.fixture
def admin_user():
    return create_user("admin@test.com", role="ADMIN")


@pytest.fixture
def customer_headers(customer):
    return auth_headers(customer)


@pytest.fixture
def admin_headers(admin_user):
    return auth_headers(admin_user)


def card_payload(number=VISA_CARD, cvv="123", **extra):
    data = {
        "card_holder_name": "Test User",
        "card_number": number,
        "expiry_month": 12,
        "expiry_year": date.today().year + 3,
        "cvv": cvv,
    }
    data.update(extra)
    return data


@pytest.fixture
def card(client, customer_headers):
    response = client.post("/api/v1/cards", json=card_payload(), headers=customer_headers)
    assert response.status_code == 201, response.json()
    return response.json()["card"]
