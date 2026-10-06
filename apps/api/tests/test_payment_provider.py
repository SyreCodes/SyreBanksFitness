from dataclasses import replace

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.modules.commerce.models import Invoice, Order, Product, Subscription
from app.modules.commerce.services import CommerceService
from app.providers.payments import FlutterwaveProvider, VerifiedPayment
from tests.test_core_loop import auth, identity


def test_authenticated_webhook_verifies_server_side_and_is_idempotent(client, db, monkeypatch):
    user = identity(db, name="Buyer")
    product = Product(name="Monthly", price_minor=10000, currency="USD", billing_interval="monthly", entitlements={"coach_messaging": True})
    db.add(product)
    db.commit()
    order_data = client.post("/api/v1/orders", json={"product_id": product.id}, headers=auth(client, user)).json()
    order = db.get(Order, order_data["id"])
    monkeypatch.setattr(get_settings(), "flutterwave_webhook_secret", "test-webhook-secret")
    verified = VerifiedPayment("100", order.reference, 10000, "USD", True)
    calls = []
    def verify(_provider, transaction_id):
        calls.append(transaction_id)
        return verified
    monkeypatch.setattr(FlutterwaveProvider, "verify", verify)
    payload = {"event": "charge.completed", "data": {"id": 100, "status": "successful", "amount": 1, "currency": "RWF"}}
    assert client.post("/api/v1/payments/webhook", json=payload, headers={"verif-hash": "wrong"}).status_code == 401
    assert not calls
    for _ in range(2):
        result = client.post("/api/v1/payments/webhook", json=payload, headers={"verif-hash": "test-webhook-secret"})
        assert result.status_code == 200, result.text
    assert calls == ["100", "100"]
    assert len(db.scalars(select(Invoice)).all()) == 1
    assert len(db.scalars(select(Subscription)).all()) == 1
    assert db.scalar(select(Invoice)).amount_minor == 10000


@pytest.mark.parametrize("change", [{"reference": "other-order"}, {"currency": "RWF"}, {"amount_minor": 10001}, {"successful": False}])
def test_payment_mismatch_never_activates(db, change):
    user = identity(db, name="Buyer")
    product = Product(name="Monthly", price_minor=10000, currency="USD", billing_interval="monthly")
    db.add(product)
    db.commit()
    data = CommerceService(db).order(product.id, user)
    order = db.get(Order, data["id"])
    verified = replace(VerifiedPayment("100", order.reference, 10000, "USD", True), **change)
    with pytest.raises(AppError):
        CommerceService(db).activate(order, verified)
    assert order.status == "PENDING"
    assert db.scalar(select(Subscription)) is None
    assert db.scalar(select(Invoice)) is None
