KEY = {"X-Internal-API-Key": "test-internal-key"}
URL = "/api/v1/integration/fraud-check"


def test_internal_key_required(client, customer, card):
    body = {"user_id": customer.id, "card_id": card["id"], "amount": "100.00", "merchant_name": "Amazon"}
    assert client.post(URL, json=body).status_code == 401
    assert client.post(URL, json=body, headers={"X-Internal-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/v1/integration/health").status_code == 401


def test_fraud_check_approves_normal_payment(client, customer, card):
    response = client.post(URL, headers=KEY, json={
        "user_id": customer.id, "card_id": card["id"], "amount": "100.00", "merchant_name": "Amazon",
    })
    assert response.status_code == 200
    assert response.json() == {"approved": True, "risk_score": 0, "reasons": []}


def test_fraud_check_high_amount_close_to_limit(client, customer, card):
    response = client.post(URL, headers=KEY, json={
        "user_id": customer.id, "card_id": card["id"], "amount": "100000.00", "merchant_name": "Jewellers",
    })
    body = response.json()
    assert body["approved"] is False
    assert "high amount" in body["reasons"]


def test_fraud_check_wrong_card_owner(client, admin_user, card):
    response = client.post(URL, headers=KEY, json={
        "user_id": admin_user.id, "card_id": card["id"], "amount": "100.00", "merchant_name": "Amazon",
    })
    assert response.json()["approved"] is False


def test_integration_health(client):
    response = client.get("/api/v1/integration/health", headers=KEY)
    assert response.status_code == 200
    assert response.json()["database"] is True


def test_public_health(client):
    assert client.get("/health").json()["status"] == "ok"
