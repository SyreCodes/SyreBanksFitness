from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.security import access_token
from app.modules.admin.models import AuditLog
from app.modules.auth.models import User
from app.modules.clients.models import ClientProfile
from app.modules.cms.models import MediaAsset
from app.modules.coaching.models import Exercise
from app.modules.commerce.models import Order, Product, Subscription
from app.modules.experience.models import Checkin, Message
from app.modules.formchecks.models import FormCheck
from app.modules.leads.models import Lead


def actor(db, name: str, role: str, coach_id: str | None = None, status: str = "ACTIVE") -> User:
    user = User(name=name, email=f"{name.lower().replace(' ', '.')}@example.com", role=role,
                password_hash="not-used-by-bearer-tests", assigned_coach_id=coach_id, status=status)
    db.add(user)
    db.flush()
    if role == "CLIENT":
        db.add(ClientProfile(client_id=user.id))
    db.commit()
    return user


def bearer(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token(user)}"}


def form_check(db, coach: User, member: User) -> None:
    exercise = Exercise(name="Squat", muscle_group="Legs", owner_id=coach.id)
    asset = MediaAsset(owner_id=member.id, storage_key=f"{member.id}-form.mp4", content_type="video/mp4", size=100,
                       purpose="private", public=False)
    db.add_all([exercise, asset])
    db.flush()
    db.add(FormCheck(client_id=member.id, exercise_id=exercise.id, exercise_name="Squat", media_asset_id=asset.id))


def test_dashboard_counts_real_work_and_scopes_coaches(client, db):
    admin = actor(db, "Super Admin", "SUPER_ADMIN")
    first_coach = actor(db, "First Coach", "COACH")
    second_coach = actor(db, "Second Coach", "COACH")
    first = actor(db, "First Client", "CLIENT", first_coach.id)
    second = actor(db, "Second Client", "CLIENT", second_coach.id)
    db.add_all([
        Lead(name="First Lead", email="first-lead@example.com", assigned_coach_id=first_coach.id, stage="NEW", consent_version="test"),
        Lead(name="Second Lead", email="second-lead@example.com", assigned_coach_id=second_coach.id, stage="WON", consent_version="test"),
        Checkin(client_id=first.id, answers={}), Checkin(client_id=second.id, answers={}),
        Message(sender_id=first.id, recipient_id=first_coach.id, body="Please review"),
        Message(sender_id=second.id, recipient_id=second_coach.id, body="Please review"),
    ])
    form_check(db, first_coach, first)
    form_check(db, second_coach, second)
    product = Product(name="Monthly", price_minor=10000, currency="USD", billing_interval="monthly")
    db.add(product)
    db.flush()
    for member in [first, second]:
        failed = Order(client_id=member.id, product_id=product.id, snapshot={}, amount_minor=10000, currency="USD",
                       status="FAILED", reference=f"failed-{member.id}")
        paid = Order(client_id=member.id, product_id=product.id, snapshot={}, amount_minor=10000, currency="USD",
                     status="PAID", reference=f"paid-{member.id}")
        db.add_all([failed, paid])
        db.flush()
        db.add(Subscription(client_id=member.id, product_id=product.id, order_id=paid.id, status="ACTIVE",
                            current_period_start=datetime.now(UTC) - timedelta(days=1),
                            current_period_end=datetime.now(UTC) + timedelta(days=20), entitlements={}))
    db.commit()

    response = client.get("/api/v1/admin/dashboard", headers=bearer(first_coach))
    assert response.status_code == 200, response.text
    data = response.json()
    assert {key: data["metrics"][key] for key in ["total_clients", "new_leads", "checkins_pending", "formchecks_pending", "unread_messages", "failed_payments", "active_subscriptions"]} == {
        "total_clients": 1, "new_leads": 1, "checkins_pending": 1, "formchecks_pending": 1,
        "unread_messages": 1, "failed_payments": 1, "active_subscriptions": 1,
    }
    assert data["metrics"]["annualized_recurring_revenue_minor"] is None
    assert data["metrics"]["lead_conversion"] == 0
    assert sum(item["count"] for item in data["new_clients_trend"]) == 1
    assert next(item for item in data["lead_funnel"] if item["stage"] == "NEW")["count"] == 1
    assert len(data["attention"]) == 1 and data["attention"][0]["client_id"] == first.id
    assert all(action["key"] != "failed_payments" for action in data["priority_actions"])
    assert client.get("/api/v1/admin/dashboard", headers=bearer(admin)).json()["metrics"]["total_clients"] == 2
    assert client.get("/api/v1/admin/dashboard", headers=bearer(first)).status_code == 403


def test_super_admin_user_management_revokes_tokens_and_audits_changes(client, db):
    owner = actor(db, "Owner Admin", "SUPER_ADMIN")
    admin = actor(db, "Business Admin", "ADMIN")
    member = actor(db, "Member User", "CLIENT")
    old_token = bearer(member)
    assert client.get("/api/v1/admin/users", headers=bearer(admin)).status_code == 403
    assert client.patch(f"/api/v1/admin/users/{member.id}", headers=bearer(admin), json={"role": "COACH"}).status_code == 403

    listing = client.get("/api/v1/admin/users", headers=bearer(owner), params={"search": "member", "role": "CLIENT", "limit": 1})
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == member.id
    assert "password_hash" not in listing.json()["items"][0]
    changed = client.patch(f"/api/v1/admin/users/{member.id}", headers=bearer(owner), json={"role": "COACH"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["role"] == "COACH"
    assert client.get("/api/v1/auth/me", headers=old_token).status_code == 401
    assert client.patch(f"/api/v1/admin/users/{owner.id}", headers=bearer(owner), json={"active": False}).status_code == 409
    assert client.patch(f"/api/v1/admin/users/{member.id}", headers=bearer(owner), json={"active": None}).status_code == 422
    deactivated = client.patch(f"/api/v1/admin/users/{member.id}", headers=bearer(owner), json={"active": False})
    assert deactivated.status_code == 200
    assert deactivated.json()["active"] is False
    assert client.get("/api/v1/auth/me", headers=bearer(member)).status_code == 401
    assert client.get("/api/v1/admin/users", headers=bearer(owner), params={"active": "false"}).json()["total"] == 1
    audit = client.get("/api/v1/audit", headers=bearer(owner), params={"resource_type": "User", "resource_id": member.id})
    assert audit.status_code == 200, audit.text
    assert {item["action"] for item in audit.json()["items"]} == {"user.role_changed", "user.deactivated"}
    assert all(item["actor_name"] == "Owner Admin" for item in audit.json()["items"])
    details = {item["action"]: item["details"] for item in audit.json()["items"]}
    assert details["user.role_changed"] == {"previous_role": "CLIENT", "new_role": "COACH"}
    assert details["user.deactivated"] == {"previous_active": True, "new_active": False}
    assert client.get("/api/v1/audit", headers=bearer(owner), params={"search": "Owner Admin"}).json()["total"] >= 2
    assert len(db.scalars(select(AuditLog).where(AuditLog.resource_id == member.id)).all()) == 2


def test_client_attention_and_status_filters_have_server_backed_totals(client, db):
    coach = actor(db, "Filter Coach", "COACH")
    other_coach = actor(db, "Other Coach", "COACH")
    active = actor(db, "Active Member", "CLIENT", coach.id)
    paused = actor(db, "Paused Member", "CLIENT", coach.id, "PAUSED")
    onboarding = actor(db, "New Member", "CLIENT", coach.id, "ONBOARDING")
    actor(db, "Outside Member", "CLIENT", other_coach.id)
    headers = bearer(coach)
    attention = client.get("/api/v1/clients", headers=headers, params={"attention": "needs_attention", "limit": 1})
    assert attention.status_code == 200, attention.text
    assert attention.json()["total"] == 2
    second_page = client.get("/api/v1/clients", headers=headers, params={"attention": "needs_attention", "limit": 1, "offset": 1})
    assert second_page.status_code == 200
    assert second_page.json()["total"] == 2
    ids = {attention.json()["items"][0]["id"], second_page.json()["items"][0]["id"]}
    assert ids == {active.id, onboarding.id}
    assert all(row["attention_reasons"] and row["attention_status"] == "NEEDS_ATTENTION" for row in [attention.json()["items"][0], second_page.json()["items"][0]])
    active_only = client.get("/api/v1/clients", headers=headers, params={"status": "ACTIVE", "attention": "needs_attention"}).json()
    assert active_only["total"] == 1 and active_only["items"][0]["id"] == active.id
    paused_only = client.get("/api/v1/clients", headers=headers, params={"status": "PAUSED"}).json()
    assert paused_only["total"] == 1 and paused_only["items"][0]["id"] == paused.id
    assert paused_only["items"][0]["attention_status"] == "ON_TRACK"
