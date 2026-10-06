import secrets

from fastapi import APIRouter, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.permissions import DB, Identity, OptionalIdentity
from app.modules.commerce.entitlements import EntitlementService
from app.modules.commerce.models import Invoice, Order, Subscription
from app.modules.commerce.schemas import (
    OrderInput,
    PaymentInitialize,
    PaymentVerify,
    ProductInput,
    ProductPatch,
    RefundRequest,
    SubscriptionCancel,
)
from app.modules.commerce.services import CommerceService

router = APIRouter(tags=["Commerce"])


@router.get("/products")
def products(db: DB, user: OptionalIdentity, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return CommerceService(db).products(user, limit, offset)


@router.post("/products", status_code=201)
def product(data: ProductInput, db: DB, user: Identity):
    return CommerceService(db).product(data, user)


@router.patch("/products/{product_id}")
def patch_product(product_id: str, data: ProductPatch, db: DB, user: Identity):
    return CommerceService(db).patch_product(product_id, data, user)


@router.get("/orders")
def orders(db: DB, user: Identity, client_id: str | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return CommerceService(db).list_owned(Order, user, client_id, limit, offset)


@router.post("/orders", status_code=201)
def order(data: OrderInput, db: DB, user: Identity):
    return CommerceService(db).order(data.product_id, user)


@router.get("/payments/status")
def payment_status():
    settings = get_settings()
    available = bool(settings.flutterwave_secret_key and settings.flutterwave_webhook_secret)
    return {"available": available, "provider": "flutterwave", "reason": "" if available else "Payment credentials are not configured"}


@router.post("/payments/initialize")
def initialize(data: PaymentInitialize, db: DB, user: Identity):
    if not payment_status()["available"]:
        raise AppError(503, "PAYMENT_UNAVAILABLE", "Payment credentials are not configured. Contact the coach.")
    return CommerceService(db).initialize(data.order_id, user)


@router.post("/payments/verify")
def verify(data: PaymentVerify, db: DB, user: Identity):
    return CommerceService(db).verify(data.order_id, data.transaction_id, user)


@router.post("/payments/webhook")
async def webhook(request: Request, db: DB):
    secret = get_settings().flutterwave_webhook_secret
    received = request.headers.get("verif-hash", "")
    if not secret or not received or not secrets.compare_digest(received, secret):
        raise AppError(401, "INVALID_WEBHOOK", "Invalid webhook authentication")
    try:
        payload = await request.json()
        transaction_id = str(payload["data"]["id"])
        if not transaction_id.isdecimal():
            raise ValueError("Invalid ID")
    except (ValueError, KeyError, TypeError) as exc:
        raise AppError(422, "INVALID_WEBHOOK", "Invalid webhook payload") from exc
    return await run_in_threadpool(CommerceService(db).webhook, transaction_id)


@router.get("/subscriptions")
def subscriptions(db: DB, user: Identity, client_id: str | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return CommerceService(db).list_owned(Subscription, user, client_id, limit, offset)


@router.get("/invoices")
def invoices(db: DB, user: Identity, client_id: str | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return CommerceService(db).list_owned(Invoice, user, client_id, limit, offset)


@router.get("/entitlements")
def entitlements(db: DB, user: Identity):
    return {"entitlements": EntitlementService(db).current(user.id)}


@router.post("/subscriptions/{subscription_id}/cancel")
def cancel_subscription(subscription_id: str, data: SubscriptionCancel, db: DB, user: Identity):
    return CommerceService(db).cancel_subscription(subscription_id, user)


@router.post("/invoices/{invoice_id}/refund")
def refund(invoice_id: str, data: RefundRequest, db: DB, user: Identity):
    return CommerceService(db).refund(invoice_id, user)


@router.get("/invoices/{invoice_id}/download")
def download_invoice(invoice_id: str, db: DB, user: Identity):
    content, number = CommerceService(db).download_invoice(invoice_id, user)
    return Response(content=content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{number}.pdf"', "X-Content-Type-Options": "nosniff"})
