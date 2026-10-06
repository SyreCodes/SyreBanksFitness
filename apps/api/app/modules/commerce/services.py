import copy
import logging
from datetime import UTC, datetime
from uuid import uuid4

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.permissions import ADMIN_ROLES, client_scope, require_admin, scoped
from app.core.repository import audit, paginate, persist, require_record, serialize
from app.modules.auth.models import EmailOutbox, User
from app.modules.commerce.models import Invoice, Order, Payment, Product, Subscription
from app.modules.commerce.schemas import ProductInput, ProductPatch
from app.modules.experience.models import Notification
from app.providers.email import deliver_outbox
from app.providers.payments import CURRENCY_FACTORS, FlutterwaveProvider, PaymentProvider, VerifiedPayment


class CommerceService:
    def __init__(self, db: Session, provider: PaymentProvider | None = None):
        self.db, self.provider = db, provider or FlutterwaveProvider()

    def products(self, user: User | None, limit: int, offset: int) -> dict:
        stmt = select(Product)
        if not user or user.role not in ADMIN_ROLES:
            stmt = stmt.where(Product.active.is_(True))
        result = paginate(self.db, stmt.order_by(Product.price_minor), limit, offset)
        for item in result["items"]:
            item["price"] = item["price_minor"] / CURRENCY_FACTORS[item["currency"]]
        return result

    def product(self, data: ProductInput, user: User) -> dict:
        require_admin(user)
        return persist(self.db, Product(**data.model_dump()), user.id, "product.created")

    def patch_product(self, product_id: str, data: ProductPatch, user: User) -> dict:
        require_admin(user)
        product = require_record(self.db, Product, product_id)
        for key, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
            setattr(product, key, value)
        return persist(self.db, product, user.id, "product.updated")

    def order(self, product_id: str, user: User) -> dict:
        client_scope(self.db, user, user.id)
        product = require_record(self.db, Product, product_id)
        if not product.active:
            raise AppError(409, "PRODUCT_UNAVAILABLE", "This coaching plan is currently unavailable")
        snapshot = copy.deepcopy({key: value for key, value in serialize(product).items() if key not in {"created_at", "updated_at"}})
        order = Order(client_id=user.id, product_id=product.id, snapshot=snapshot, amount_minor=product.price_minor, currency=product.currency, reference=f"SBF-{uuid4()}")
        return persist(self.db, order, user.id, "order.created")

    def initialize(self, order_id: str, user: User) -> dict:
        order = require_record(self.db, Order, order_id)
        client_scope(self.db, user, order.client_id)
        if order.client_id != user.id:
            raise AppError(403, "ORDER_OWNER_REQUIRED", "Only the order owner can start checkout")
        if order.status != "PENDING":
            raise AppError(409, "ORDER_ALREADY_PAID", "This order has already been paid")
        checkout_url = self.provider.initialize(order.reference, order.amount_minor, order.currency, user.email, user.name)
        return {"order_id": order.id, "checkout_url": checkout_url, "reference": order.reference}

    def activate(self, order: Order, verified: VerifiedPayment) -> dict:
        if not verified.successful or verified.reference != order.reference or verified.amount_minor != order.amount_minor or verified.currency != order.currency:
            raise AppError(409, "PAYMENT_MISMATCH", "The verified payment does not match this order")
        # Order row locking plus unique payment/order/transaction constraints ensure idempotency.
        if order.status == "PAID":
            existing = self.db.scalar(select(Payment).where(Payment.order_id == order.id))
            if not existing or existing.provider_transaction_id != verified.transaction_id:
                raise AppError(409, "PAYMENT_MISMATCH", "This order was paid with a different transaction")
            return {"order_id": order.id, "status": "PAID", "already_processed": True}
        other = self.db.scalar(select(Payment).where(Payment.provider_transaction_id == verified.transaction_id))
        if other:
            raise AppError(409, "PAYMENT_ALREADY_USED", "This transaction has already been processed")
        now = datetime.now(UTC)
        interval = order.snapshot.get("billing_interval", "monthly")
        end = now + (relativedelta(years=1) if interval == "annual" else relativedelta(months=1))
        self.db.add(Payment(order_id=order.id, provider_transaction_id=verified.transaction_id, status="VERIFIED", amount_minor=order.amount_minor, currency=order.currency))
        self.db.add(Subscription(client_id=order.client_id, product_id=order.product_id, order_id=order.id, status="ACTIVE", current_period_start=now, current_period_end=end, entitlements=order.snapshot.get("entitlements", {})))
        self.db.add(Invoice(client_id=order.client_id, order_id=order.id, number=f"SBF-{now.year}-{order.id[:8].upper()}", amount_minor=order.amount_minor, currency=order.currency, issued_at=now, items=[{"name": order.snapshot["name"], "quantity": 1, "price_minor": order.amount_minor}]))
        self.db.add(Notification(user_id=order.client_id, title="Payment verified. Your coaching plan is active.", body="Complete onboarding and review your coaching tasks", link="/app/onboarding"))
        order.status = "PAID"
        client = self.db.get(User, order.client_id)
        if client:
            client.status = "ACTIVE"
        audit(self.db, order.client_id, "payment.verified", order)
        email = None
        if client and get_settings().smtp_host:
            email = EmailOutbox(user_id=client.id, recipient=client.email, subject="Your Syre Banks Fitness coaching plan is active", body=f"Your payment for {order.snapshot['name']} was verified. View your invoice and complete onboarding at {get_settings().public_web_url}/app/billing.")
            self.db.add(email)
        self.db.commit()
        if email:
            try:
                deliver_outbox.delay(email.id)
            except Exception:
                logging.getLogger("sbf.mail").warning("Confirmation queued in durable outbox; broker dispatch will retry")
        return {"order_id": order.id, "status": "PAID", "already_processed": False, "confirmation_email_status": "QUEUED" if email else "NOT_CONFIGURED"}

    def verify(self, order_id: str, transaction_id: str, user: User) -> dict:
        order = self.db.scalar(select(Order).where(Order.id == order_id).with_for_update())
        if not order:
            raise AppError(404, "ORDER_NOT_FOUND", "Order not found")
        client_scope(self.db, user, order.client_id)
        return self.activate(order, self.provider.verify(transaction_id))

    def webhook(self, transaction_id: str) -> dict:
        verified = self.provider.verify(transaction_id)
        order = self.db.scalar(select(Order).where(Order.reference == verified.reference).with_for_update())
        if not order:
            raise AppError(404, "ORDER_NOT_FOUND", "Order not found")
        return self.activate(order, verified)

    def list_owned(self, model, user: User, client_id: str | None, limit: int, offset: int) -> dict:
        result = paginate(self.db, scoped(self.db, user, select(model), model.client_id, client_id).order_by(model.created_at.desc()), limit, offset)
        if model not in {Subscription, Invoice} or not result["items"]:
            return result

        client_ids = {item["client_id"] for item in result["items"]}
        client_names = {client.id: client.name for client in self.db.scalars(select(User).where(User.id.in_(client_ids))).all()}
        for item in result["items"]:
            item["client_name"] = client_names.get(item["client_id"])

        if model is Subscription:
            order_ids = {item["order_id"] for item in result["items"]}
            orders = {order.id: order for order in self.db.scalars(select(Order).where(Order.id.in_(order_ids))).all()}
            product_ids = {item["product_id"] for item in result["items"]}
            product_names = {product.id: product.name for product in self.db.scalars(select(Product).where(Product.id.in_(product_ids))).all()}
            for item in result["items"]:
                snapshot = orders[item["order_id"]].snapshot if item["order_id"] in orders else {}
                item["product_name"] = snapshot.get("name") or product_names.get(item["product_id"])
        return result

    def cancel_subscription(self, subscription_id: str, user: User) -> dict:
        subscription = require_record(self.db, Subscription, subscription_id)
        client_scope(self.db, user, subscription.client_id)
        if user.id != subscription.client_id and user.role not in ADMIN_ROLES:
            raise AppError(403, "SUBSCRIPTION_OWNER_REQUIRED", "Only the subscriber or an administrator can cancel this plan")
        if subscription.status not in {"ACTIVE", "CANCEL_AT_PERIOD_END"}:
            raise AppError(409, "SUBSCRIPTION_NOT_ACTIVE", "This subscription is not active")
        subscription.status = "CANCEL_AT_PERIOD_END"
        result = persist(self.db, subscription, user.id, "subscription.cancelled_at_period_end")
        return {**result, "message": "Your coaching plan ends at the current paid period end. Payment history and invoices are preserved.", "effective_at": subscription.current_period_end, "provider_recurring_charge": False}

    def refund(self, invoice_id: str, user: User) -> dict:
        require_admin(user)
        invoice = require_record(self.db, Invoice, invoice_id)
        payment = self.db.scalar(select(Payment).where(Payment.order_id == invoice.order_id))
        if not payment:
            raise AppError(404, "PAYMENT_NOT_FOUND", "Verified payment not found")
        from app.providers.payments import UnavailableBillingOperations
        return UnavailableBillingOperations().refund(payment.provider_transaction_id, payment.amount_minor, payment.currency)

    def download_invoice(self, invoice_id: str, user: User) -> tuple[bytes, str]:
        invoice = require_record(self.db, Invoice, invoice_id)
        client = client_scope(self.db, user, invoice.client_id)
        from app.modules.cms.services import CMSService
        from app.providers.invoices import invoice_pdf
        return invoice_pdf(invoice, client, CMSService(self.db).settings()), invoice.number
