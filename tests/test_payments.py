from decimal import Decimal

from app.models import Card, Payment, Transaction
from tests.conftest import auth_headers, create_user

URL = "/api/v1/payments"


def pay(client, headers, card_id, amount="2500.00", cvv="123", extra_headers=None):
    all_headers = {**headers, **(extra_headers or {})}
    return client.post(URL, json={"card_id": card_id, "amount": amount, "merchant_name": "Amazon", "cvv": cvv},
                       headers=all_headers)


def test_successful_payment(client, customer_headers, card, db):
    response = pay(client, customer_headers, card["id"])
    assert response.status_code == 201
    payment = response.json()["payment"]
    assert payment["status"] == "SUCCESS"
    assert payment["processed_by"] == "fastapi"
    assert payment["risk_score"] == 0

    assert db.get(Card, card["id"]).available_credit == Decimal("97500.00")
    txn = db.query(Transaction).filter(Transaction.payment_id == payment["id"]).one()
    assert txn.transaction_type == "PURCHASE"
    assert txn.available_credit_after == Decimal("97500.00")


def test_insufficient_credit(client, customer_headers, card, db):
    db.query(Card).filter(Card.id == card["id"]).update({"available_credit": Decimal("100.00")})
    db.commit()
    response = pay(client, customer_headers, card["id"], amount="500.00")
    assert response.status_code == 402
    assert response.json()["payment"]["status"] == "FAILED"
    db.expire_all()
    assert db.get(Card, card["id"]).available_credit == Decimal("100.00")


def test_validation_errors(client, customer_headers, card, db):
    assert pay(client, customer_headers, card["id"], cvv="12").status_code == 422
    assert pay(client, customer_headers, card["id"], amount="0").status_code == 422
    assert pay(client, customer_headers, card["id"], amount="999999.00").status_code == 422
    assert pay(client, customer_headers, card["id"], cvv="12a").status_code == 400

    db.query(Card).filter(Card.id == card["id"]).update({"status": "BLOCKED"})
    db.commit()
    assert pay(client, customer_headers, card["id"]).status_code == 400


def test_cannot_pay_with_other_users_card(client, card):
    other = auth_headers(create_user("other@test.com"))
    assert pay(client, other, card["id"]).status_code == 404


def test_fraud_rule_too_many_payments(client, customer_headers, card):
    for _ in range(5):
        assert pay(client, customer_headers, card["id"], amount="10.00").status_code == 201
    response = pay(client, customer_headers, card["id"], amount="10.00")
    assert response.status_code == 402
    assert "fraud" in response.json()["payment"]["failure_reason"].lower()


def test_idempotency_key(client, customer_headers, card, db):
    first = pay(client, customer_headers, card["id"], extra_headers={"Idempotency-Key": "order-1001"})
    second = pay(client, customer_headers, card["id"], extra_headers={"Idempotency-Key": "order-1001"})
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["payment"]["id"] == second.json()["payment"]["id"]
    assert db.query(Payment).count() == 1


def test_list_and_detail(client, customer_headers, card):
    payment_id = pay(client, customer_headers, card["id"]).json()["payment"]["id"]
    pay(client, customer_headers, card["id"], amount="100.00")
    listing = client.get(f"{URL}?status=success", headers=customer_headers).json()
    assert listing["count"] == 2
    detail = client.get(f"{URL}/{payment_id}", headers=customer_headers)
    assert detail.status_code == 200
    assert detail.json()["merchant_name"] == "Amazon"

    other = auth_headers(create_user("other@test.com"))
    assert client.get(f"{URL}/{payment_id}", headers=other).status_code == 404


def test_refund_admin_only(client, customer_headers, admin_headers, card, db):
    payment_id = pay(client, customer_headers, card["id"]).json()["payment"]["id"]
    assert client.post(f"{URL}/{payment_id}/refund", headers=customer_headers).status_code == 403

    response = client.post(f"{URL}/{payment_id}/refund", json={"reason": "Order cancelled"}, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["payment"]["status"] == "REFUNDED"
    assert response.json()["transaction"]["transaction_type"] == "REFUND"
    db.expire_all()
    assert db.get(Card, card["id"]).available_credit == Decimal("100000.00")

    assert client.post(f"{URL}/{payment_id}/refund", headers=admin_headers).status_code == 400
