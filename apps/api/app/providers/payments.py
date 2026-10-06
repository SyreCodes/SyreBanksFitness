from dataclasses import dataclass
from decimal import Decimal
from typing import NoReturn, Protocol

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppError

CURRENCY_FACTORS = {"USD": 100, "RWF": 1}


@dataclass(frozen=True)
class VerifiedPayment:
    transaction_id: str
    reference: str
    amount_minor: int
    currency: str
    successful: bool


class PaymentProvider(Protocol):
    def initialize(self, reference: str, amount_minor: int, currency: str, email: str, name: str) -> str: ...
    def verify(self, transaction_id: str) -> VerifiedPayment: ...


class FlutterwaveProvider:
    """Flutterwave v3 Standard; frontend redirect status is never proof of payment."""
    def __init__(self) -> None:
        self.settings = get_settings()

    def request(self, method: str, path: str, payload: dict | None = None) -> dict:
        if not self.settings.flutterwave_secret_key:
            raise AppError(503, "PAYMENT_UNAVAILABLE", "Payments are not configured. Contact the coach.")
        try:
            response = httpx.request(method, f"https://api.flutterwave.com/v3/{path}", headers={"Authorization": f"Bearer {self.settings.flutterwave_secret_key}"}, json=payload, timeout=20)
            response.raise_for_status()
            body = response.json()
            if body.get("status") != "success" or not isinstance(body.get("data"), dict):
                raise ValueError("Provider rejected transaction")
            return body["data"]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise AppError(502, "PAYMENT_PROVIDER_ERROR", "The payment provider could not complete this request") from exc

    def initialize(self, reference: str, amount_minor: int, currency: str, email: str, name: str) -> str:
        data = self.request("POST", "payments", {"tx_ref": reference, "amount": str(Decimal(amount_minor) / CURRENCY_FACTORS[currency]), "currency": currency, "redirect_url": f"{self.settings.public_web_url}/app/billing", "customer": {"email": email, "name": name}, "customizations": {"title": "Syre Banks Fitness"}})
        link = data.get("link")
        if not isinstance(link, str) or not link.startswith("https://"):
            raise AppError(502, "INVALID_CHECKOUT_URL", "The payment provider returned an invalid checkout link")
        return link

    def verify(self, transaction_id: str) -> VerifiedPayment:
        if not transaction_id.isdecimal():
            raise AppError(422, "INVALID_TRANSACTION_ID", "Invalid payment transaction ID")
        data = self.request("GET", f"transactions/{transaction_id}/verify")
        try:
            currency = str(data["currency"]).upper()
            amount = Decimal(str(data["amount"])) * CURRENCY_FACTORS[currency]
            if amount != amount.to_integral_value():
                raise ValueError("Non-integral minor amount")
            return VerifiedPayment(str(data["id"]), str(data["tx_ref"]), int(amount), currency, data["status"] == "successful")
        except (KeyError, ValueError, ArithmeticError) as exc:
            raise AppError(502, "INVALID_PAYMENT_RESPONSE", "The payment verification response was invalid") from exc


class BillingOperationsProvider(Protocol):
    def refund(self, transaction_id: str, amount_minor: int, currency: str) -> None: ...
    def cancel_recurring(self, provider_subscription_id: str) -> None: ...


class UnavailableBillingOperations:
    def refund(self, transaction_id: str, amount_minor: int, currency: str) -> NoReturn:
        raise AppError(503, "REFUND_UNAVAILABLE", "Provider refunds require a configured and tested refund adapter. Contact the coach.")

    def cancel_recurring(self, provider_subscription_id: str) -> NoReturn:
        raise AppError(503, "RECURRING_CANCELLATION_UNAVAILABLE", "External recurring-payment cancellation is not configured")
