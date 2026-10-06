from io import BytesIO

from pypdf import PdfReader
from sqlalchemy import select

from app.modules.admin.models import AuditLog
from app.modules.commerce.entitlements import EntitlementService
from app.modules.commerce.models import Invoice, Order, Product, Subscription
from app.modules.commerce.services import CommerceService
from app.providers.payments import VerifiedPayment
from tests.test_core_loop import auth, identity


def paid_plan(db, user):
    product = Product(name="Monthly Personal Coaching", price_minor=10000, currency="USD", billing_interval="monthly", entitlements={"program_access": True})
    db.add(product)
    db.commit()
    order = CommerceService(db).order(product.id, user)
    stored = db.get(Order, order["id"])
    CommerceService(db).activate(stored, VerifiedPayment("404", stored.reference, 10000, "USD", True))
    return db.scalar(select(Invoice)), db.scalar(select(Subscription))


def test_invoice_download_is_scoped_and_readable(client, db):
    member = identity(db, name="Member")
    other = identity(db, name="Other")
    invoice, _ = paid_plan(db, member)
    url = f"/api/v1/invoices/{invoice.id}/download"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=auth(client, other)).status_code == 403
    result = client.get(url, headers=auth(client, member))
    assert result.status_code == 200
    assert result.headers["content-type"] == "application/pdf"
    assert result.content.startswith(b"%PDF")
    pdf = PdfReader(BytesIO(result.content))
    assert len(pdf.pages) == 1
    text = pdf.pages[0].extract_text()
    assert "TOTAL PAID (USD)" in text
    assert "100.00" in text
    assert invoice.number in text
    assert "Monthly Personal Coaching" in text


def test_period_end_cancellation_requires_confirmation_and_preserves_invoice(client, db):
    member = identity(db, name="Member")
    other = identity(db, name="Other")
    invoice, subscription = paid_plan(db, member)
    url = f"/api/v1/subscriptions/{subscription.id}/cancel"
    headers = auth(client, member)
    assert client.post(url, json={"confirm": False}, headers=headers).status_code == 422
    assert client.post(url, json={"confirm": True}, headers=auth(client, other)).status_code == 403
    original_end = subscription.current_period_end
    result = client.post(url, json={"confirm": True}, headers=headers)
    assert result.status_code == 200
    assert subscription.status == "CANCEL_AT_PERIOD_END"
    assert subscription.current_period_end == original_end
    assert db.get(Invoice, invoice.id).status == "PAID"
    assert EntitlementService(db).current(member.id)["program_access"] is True
    assert client.post(url, json={"confirm": True}, headers=headers).status_code == 200


def test_subscription_and_invoice_lists_include_safe_names_and_preserve_purchase_snapshot(client, db):
    admin = identity(db, "ADMIN", "Admin")
    member = identity(db, name="Member")
    other = identity(db, name="Other")
    invoice, subscription = paid_plan(db, member)
    product = db.get(Product, subscription.product_id)
    product.name = "Renamed for future purchases"
    db.commit()

    subscriptions = client.get("/api/v1/subscriptions", headers=auth(client, admin))
    assert subscriptions.status_code == 200, subscriptions.text
    subscription_item = subscriptions.json()["items"][0]
    assert subscription_item["id"] == subscription.id
    assert subscription_item["client_name"] == "Member"
    assert subscription_item["product_name"] == "Monthly Personal Coaching"
    assert subscription_item["current_period_end"]
    assert "renewal_date" not in subscription_item

    invoices = client.get("/api/v1/invoices", headers=auth(client, admin))
    assert invoices.status_code == 200, invoices.text
    invoice_item = invoices.json()["items"][0]
    assert invoice_item["id"] == invoice.id
    assert invoice_item["client_name"] == "Member"
    assert invoice_item["amount_minor"] == 10000
    assert client.get("/api/v1/subscriptions", headers=auth(client, other)).json()["total"] == 0
    assert client.get("/api/v1/invoices", headers=auth(client, other)).json()["total"] == 0


def test_business_audit_has_safe_request_id(client, db):
    user = identity(db, name="Member")
    result = client.post("/api/v1/progress", json={"value": 75, "unit": "kg"}, headers=auth(client, user))
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "progress.logged"))
    assert audit.request_id == result.headers["X-Request-ID"]
