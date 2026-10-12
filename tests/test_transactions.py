from datetime import date

from tests.conftest import auth_headers, create_user

URL = "/api/v1/transactions"


def make_payments(client, headers, card_id, amounts):
    for amount in amounts:
        response = client.post("/api/v1/payments", headers=headers, json={
            "card_id": card_id, "amount": amount, "merchant_name": "Flipkart", "cvv": "123",
        })
        assert response.status_code == 201


def test_list_transactions(client, customer_headers, card):
    make_payments(client, customer_headers, card["id"], ["1000.00", "250.50"])
    body = client.get(URL, headers=customer_headers).json()
    assert body["count"] == 2
    assert body["results"][0]["card_masked_number"] == "**** **** **** 1111"
    assert body["results"][0]["payment_reference"].startswith("PAY")


def test_filters(client, customer_headers, card):
    make_payments(client, customer_headers, card["id"], ["1000.00", "250.50"])
    today = date.today().isoformat()
    assert client.get(f"{URL}?min_amount=500", headers=customer_headers).json()["count"] == 1
    assert client.get(f"{URL}?type=refund", headers=customer_headers).json()["count"] == 0
    assert client.get(f"{URL}?from_date={today}&to_date={today}", headers=customer_headers).json()["count"] == 2
    assert client.get(f"{URL}?from_date=2001-01-01&to_date=2001-01-31", headers=customer_headers).json()["count"] == 0
    assert client.get(f"{URL}?from_date=07-10-2026", headers=customer_headers).status_code == 422
    assert client.get(f"{URL}?from_date=2026-02-01&to_date=2026-01-01", headers=customer_headers).status_code == 400


def test_pagination(client, customer_headers, card):
    make_payments(client, customer_headers, card["id"], ["10.00", "20.00", "30.00"])
    body = client.get(f"{URL}?page=2&page_size=2", headers=customer_headers).json()
    assert body["count"] == 3
    assert body["total_pages"] == 2
    assert len(body["results"]) == 1


def test_detail_only_mine(client, customer_headers, card):
    make_payments(client, customer_headers, card["id"], ["1000.00"])
    txn_id = client.get(URL, headers=customer_headers).json()["results"][0]["id"]
    assert client.get(f"{URL}/{txn_id}", headers=customer_headers).status_code == 200
    other = auth_headers(create_user("other@test.com"))
    assert client.get(f"{URL}/{txn_id}", headers=other).status_code == 404


def test_summary(client, customer_headers, card):
    make_payments(client, customer_headers, card["id"], ["1000.00", "500.00"])
    body = client.get(f"{URL}/summary", headers=customer_headers).json()
    assert body["total_spent"] == "1500.00"
    assert body["total_transactions"] == 2
    assert body["count_by_type"] == {"PURCHASE": 2}
