from decimal import Decimal

from app.models import Card, User

ADMIN = "/api/v1/admin"


def make_payment(client, headers, card_id, amount="3000.00"):
    response = client.post("/api/v1/payments", headers=headers, json={
        "card_id": card_id, "amount": amount, "merchant_name": "Myntra", "cvv": "123",
    })
    assert response.status_code == 201


def test_customer_cannot_access_admin(client, customer_headers):
    for path in ["/dashboard", "/users", "/cards", "/payments", "/transactions", "/audit-logs"]:
        assert client.get(ADMIN + path, headers=customer_headers).status_code == 403, path


def test_dashboard(client, customer_headers, admin_headers, card):
    make_payment(client, customer_headers, card["id"])
    body = client.get(f"{ADMIN}/dashboard", headers=admin_headers).json()
    assert body["users"]["total"] == 2
    assert body["payments"]["success"] == 1
    assert body["payments"]["total_amount"] == "3000.00"
    assert body["payments"]["today_amount"] == "3000.00"


def test_users(client, customer, admin_headers, card):
    assert client.get(f"{ADMIN}/users", headers=admin_headers).json()["count"] == 2
    found = client.get(f"{ADMIN}/users?search=customer", headers=admin_headers).json()
    assert found["count"] == 1
    assert found["results"][0]["total_cards"] == 1

    detail = client.get(f"{ADMIN}/users/{customer.id}", headers=admin_headers).json()
    assert len(detail["cards"]) == 1
    assert detail["total_spent"] == "0.00"
    assert client.get(f"{ADMIN}/users/9999", headers=admin_headers).status_code == 404


def test_block_user_stops_api_access(client, customer, customer_headers, admin_headers):
    response = client.post(f"{ADMIN}/users/{customer.id}/status", json={"is_active": False}, headers=admin_headers)
    assert response.status_code == 200
    assert client.get("/api/v1/auth/profile", headers=customer_headers).status_code == 403

    client.post(f"{ADMIN}/users/{customer.id}/status", json={"is_active": True}, headers=admin_headers)
    assert client.get("/api/v1/auth/profile", headers=customer_headers).status_code == 200


def test_admin_cannot_change_self(client, admin_user, admin_headers):
    assert client.post(f"{ADMIN}/users/{admin_user.id}/status", json={"is_active": False}, headers=admin_headers).status_code == 400
    assert client.post(f"{ADMIN}/users/{admin_user.id}/role", json={"role": "CUSTOMER"}, headers=admin_headers).status_code == 400


def test_change_role(client, customer, admin_headers, db):
    assert client.post(f"{ADMIN}/users/{customer.id}/role", json={"role": "ADMIN"}, headers=admin_headers).status_code == 200
    assert db.get(User, customer.id).role == "ADMIN"
    assert client.post(f"{ADMIN}/users/{customer.id}/role", json={"role": "BOSS"}, headers=admin_headers).status_code == 422


def test_card_status_and_limit(client, customer_headers, admin_headers, card, db):
    url = f"{ADMIN}/cards/{card['id']}/status"
    assert client.post(url, json={"status": "BLOCKED"}, headers=admin_headers).json()["card"]["status"] == "BLOCKED"
    assert client.post(url, json={"status": "ACTIVE"}, headers=admin_headers).json()["card"]["status"] == "ACTIVE"

    make_payment(client, customer_headers, card["id"])
    limit_url = f"{ADMIN}/cards/{card['id']}/credit-limit"
    response = client.post(limit_url, json={"credit_limit": "150000.00"}, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["card"]["available_credit"] == "147000.00"
    assert client.post(limit_url, json={"credit_limit": "2000.00"}, headers=admin_headers).status_code == 400
    db.expire_all()
    assert db.get(Card, card["id"]).credit_limit == Decimal("150000.00")


def test_lists_and_audit_logs(client, customer, customer_headers, admin_headers, card):
    make_payment(client, customer_headers, card["id"])
    payments = client.get(f"{ADMIN}/payments", headers=admin_headers).json()
    assert payments["count"] == 1
    assert payments["results"][0]["user_email"] == "customer@test.com"
    payment_id = payments["results"][0]["id"]
    assert client.get(f"{ADMIN}/payments/{payment_id}", headers=admin_headers).status_code == 200
    assert client.get(f"{ADMIN}/cards?brand=visa", headers=admin_headers).json()["count"] == 1
    assert client.get(f"{ADMIN}/transactions?user_id={customer.id}", headers=admin_headers).json()["count"] == 1
    logs = client.get(f"{ADMIN}/audit-logs?action=payment_success", headers=admin_headers).json()
    assert logs["count"] == 1
    assert logs["results"][0]["source"] == "fastapi"
