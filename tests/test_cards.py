from decimal import Decimal

from app.core.encryption import decrypt_card_number
from app.models import Card, Transaction
from tests.conftest import AMEX_CARD, MASTER_CARD, VISA_CARD, auth_headers, card_payload, create_user


def test_add_card(client, customer_headers, db):
    response = client.post("/api/v1/cards", json=card_payload(), headers=customer_headers)
    assert response.status_code == 201
    card = response.json()["card"]
    assert card["card_brand"] == "VISA"
    assert card["masked_number"] == "**** **** **** 1111"
    assert card["is_default"] is True
    assert card["available_credit"] == "100000.00"
    assert "card_number" not in card

    saved = db.get(Card, card["id"])
    assert VISA_CARD not in saved.card_number_encrypted
    assert decrypt_card_number(saved.card_number_encrypted) == VISA_CARD


def test_add_card_validation(client, customer_headers):
    assert client.post("/api/v1/cards", json=card_payload("4111111111111112"), headers=customer_headers).status_code == 400
    assert client.post("/api/v1/cards", json=card_payload(expiry_year=2020, expiry_month=1), headers=customer_headers).status_code == 400
    assert client.post("/api/v1/cards", json=card_payload(AMEX_CARD, cvv="123"), headers=customer_headers).status_code == 400
    assert client.post("/api/v1/cards", json=card_payload(AMEX_CARD, cvv="1234"), headers=customer_headers).status_code == 201
    assert client.post("/api/v1/cards", json=card_payload(card_holder_name="R2D2"), headers=customer_headers).status_code == 422


def test_duplicate_card(client, customer_headers, card):
    assert client.post("/api/v1/cards", json=card_payload(), headers=customer_headers).status_code == 400


def test_list_only_my_cards(client, card):
    other = create_user("other@test.com")
    headers = auth_headers(other)
    client.post("/api/v1/cards", json=card_payload(MASTER_CARD), headers=headers)
    body = client.get("/api/v1/cards", headers=headers).json()
    assert body["count"] == 1
    assert body["results"][0]["card_brand"] == "MASTERCARD"
    assert client.get(f"/api/v1/cards/{card['id']}", headers=headers).status_code == 404


def test_update_and_set_default(client, customer_headers, card):
    response = client.patch(f"/api/v1/cards/{card['id']}", json={"card_holder_name": "ravi kumar"}, headers=customer_headers)
    assert response.json()["card"]["card_holder_name"] == "RAVI KUMAR"

    second = client.post("/api/v1/cards", json=card_payload(MASTER_CARD), headers=customer_headers).json()["card"]
    assert second["is_default"] is False
    client.post(f"/api/v1/cards/{second['id']}/set-default", headers=customer_headers)
    assert client.get(f"/api/v1/cards/{card['id']}", headers=customer_headers).json()["is_default"] is False
    assert client.get(f"/api/v1/cards/{second['id']}", headers=customer_headers).json()["is_default"] is True


def test_block_card(client, customer_headers, card):
    response = client.post(f"/api/v1/cards/{card['id']}/block", headers=customer_headers)
    assert response.status_code == 200
    assert response.json()["card"]["status"] == "BLOCKED"
    assert client.post(f"/api/v1/cards/{card['id']}/block", headers=customer_headers).status_code == 400


def test_remove_card(client, customer_headers, card, db):
    db.query(Card).filter(Card.id == card["id"]).update({"available_credit": Decimal("90000.00")})
    db.commit()
    assert client.delete(f"/api/v1/cards/{card['id']}", headers=customer_headers).status_code == 400

    db.query(Card).filter(Card.id == card["id"]).update({"available_credit": Decimal("100000.00")})
    db.commit()
    assert client.delete(f"/api/v1/cards/{card['id']}", headers=customer_headers).status_code == 200
    assert client.get("/api/v1/cards", headers=customer_headers).json()["count"] == 0
    assert client.post("/api/v1/cards", json=card_payload(), headers=customer_headers).status_code == 201


def test_pay_bill(client, customer_headers, card, db):
    db.query(Card).filter(Card.id == card["id"]).update({"available_credit": Decimal("90000.00")})
    db.commit()

    too_much = client.post(f"/api/v1/cards/{card['id']}/pay-bill", json={"amount": "20000.00"}, headers=customer_headers)
    assert too_much.status_code == 400

    response = client.post(f"/api/v1/cards/{card['id']}/pay-bill", json={"amount": "4000.00"}, headers=customer_headers)
    assert response.status_code == 200
    assert response.json()["card"]["available_credit"] == "94000.00"
    assert response.json()["transaction"]["transaction_type"] == "BILL_PAYMENT"
    assert db.query(Transaction).count() == 1
