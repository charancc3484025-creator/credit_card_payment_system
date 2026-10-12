import jwt

from app.core.config import settings
from app.core.security import verify_password
from tests.conftest import PASSWORD, create_user

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


def register_payload(**extra):
    data = {
        "email": "New@Test.com",
        "first_name": "Ravi",
        "last_name": "Kumar",
        "phone_number": "9876543210",
        "password": "Secure@Pass99",
        "confirm_password": "Secure@Pass99",
    }
    data.update(extra)
    return data


def test_register_success(client):
    response = client.post(REGISTER_URL, json=register_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "new@test.com"
    assert body["user"]["role"] == "CUSTOMER"
    assert "access" in body["tokens"] and "refresh" in body["tokens"]


def test_register_duplicate_email(client, customer):
    response = client.post(REGISTER_URL, json=register_payload(email="customer@test.com"))
    assert response.status_code == 400
    assert response.json()["success"] is False


def test_register_password_rules(client):
    assert client.post(REGISTER_URL, json=register_payload(confirm_password="Other@Pass99")).status_code == 422
    assert client.post(REGISTER_URL, json=register_payload(password="password1", confirm_password="password1")).status_code == 422


def test_register_bad_phone(client):
    assert client.post(REGISTER_URL, json=register_payload(phone_number="12ab")).status_code == 422


def test_register_with_admin_role(client):
    response = client.post(REGISTER_URL, json=register_payload(role="admin"))
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "ADMIN"


def test_register_invalid_role(client):
    assert client.post(REGISTER_URL, json=register_payload(role="BOSS")).status_code == 422


def test_login_success(client, customer):
    response = client.post(LOGIN_URL, json={"email": "CUSTOMER@test.com", "password": PASSWORD})
    assert response.status_code == 200
    payload = jwt.decode(response.json()["tokens"]["access"], settings.JWT_SECRET_KEY, algorithms=["HS256"])
    assert payload["token_type"] == "access"
    assert payload["user_id"] == str(customer.id)
    assert "jti" in payload and "exp" in payload


def test_login_wrong_password(client, customer):
    response = client.post(LOGIN_URL, json={"email": "customer@test.com", "password": "Wrong@Pass1"})
    assert response.status_code == 400


def test_blocked_user_cannot_login(client):
    create_user("blocked@test.com", is_active=False)
    response = client.post(LOGIN_URL, json={"email": "blocked@test.com", "password": PASSWORD})
    assert response.status_code == 403


def test_login_rate_limit(client, customer):
    for _ in range(5):
        client.post(LOGIN_URL, json={"email": "customer@test.com", "password": "Wrong@Pass1"})
    response = client.post(LOGIN_URL, json={"email": "customer@test.com", "password": PASSWORD})
    assert response.status_code == 429


def test_refresh_rotation_and_logout(client, customer):
    tokens = client.post(LOGIN_URL, json={"email": "customer@test.com", "password": PASSWORD}).json()["tokens"]

    refreshed = client.post("/api/v1/auth/token/refresh", json={"refresh": tokens["refresh"]})
    assert refreshed.status_code == 200
    assert client.post("/api/v1/auth/token/refresh", json={"refresh": tokens["refresh"]}).status_code == 401

    new = refreshed.json()
    headers = {"Authorization": f"Bearer {new['access']}"}
    assert client.post("/api/v1/auth/logout", json={"refresh": new["refresh"]}, headers=headers).status_code == 200
    assert client.post("/api/v1/auth/token/refresh", json={"refresh": new["refresh"]}).status_code == 401


def test_access_token_cannot_be_used_as_refresh(client, customer):
    tokens = client.post(LOGIN_URL, json={"email": "customer@test.com", "password": PASSWORD}).json()["tokens"]
    assert client.post("/api/v1/auth/token/refresh", json={"refresh": tokens["access"]}).status_code == 401


def test_profile(client, customer_headers):
    assert client.get("/api/v1/auth/profile").status_code == 401
    response = client.get("/api/v1/auth/profile", headers=customer_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "customer@test.com"

    updated = client.patch("/api/v1/auth/profile", json={"first_name": "Anil", "role": "ADMIN"}, headers=customer_headers)
    assert updated.status_code == 200
    assert updated.json()["first_name"] == "Anil"
    assert updated.json()["role"] == "CUSTOMER"


def test_change_password(client, customer, customer_headers, db):
    response = client.post("/api/v1/auth/change-password", headers=customer_headers, json={
        "old_password": PASSWORD, "new_password": "Changed@Pass77", "confirm_password": "Changed@Pass77",
    })
    assert response.status_code == 200
    from app.models import User
    assert verify_password("Changed@Pass77", db.get(User, customer.id).password)

    wrong = client.post("/api/v1/auth/change-password", headers=customer_headers, json={
        "old_password": "Wrong@Pass1", "new_password": "Other@Pass77", "confirm_password": "Other@Pass77",
    })
    assert wrong.status_code == 400
