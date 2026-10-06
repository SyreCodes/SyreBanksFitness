from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commerce.models import Subscription


class EntitlementService:
    """Use verified, currently active subscription snapshots to resolve paid benefits."""
    def __init__(self, db: Session):
        self.db = db

    def current(self, client_id: str, at: datetime | None = None) -> dict[str, bool | int]:
        now = at or datetime.now(UTC)
        subscriptions = self.db.scalars(select(Subscription).where(Subscription.client_id == client_id, Subscription.status.in_(["ACTIVE", "CANCEL_AT_PERIOD_END"]), Subscription.current_period_start <= now, Subscription.current_period_end > now)).all()
        result: dict[str, bool | int] = {}
        for subscription in subscriptions:
            for key, value in subscription.entitlements.items():
                if isinstance(value, bool):
                    result[key] = bool(result.get(key)) or value
                elif isinstance(value, int):
                    result[key] = max(int(result.get(key, 0)), value)
        return result
