
from io import BytesIO

from PIL import Image
from sqlalchemy import select

from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.clients.models import ClientProfile, Consent
from app.modules.commerce.models import Invoice, Order, Payment, Product, Subscription
from app.modules.commerce.services import CommerceService
from app.providers.payments import VerifiedPayment


def identity(db, role="CLIENT", name="Person", coach_id=None):
    user = User(name=name, email=f"{name.lower().replace(' ', '.')}@example.com", role=role, password_hash=hash_password("strong-test-password"), assigned_coach_id=coach_id)
    db.add(user)
    db.flush()
    if role == "CLIENT":
        db.add(ClientProfile(client_id=user.id))
    db.commit()
    return user


def auth(client, user):
    data = client.post("/api/v1/auth/login", json={"email": user.email, "password": "strong-test-password"}).json()
    return {"Authorization": f"Bearer {data['access_token']}"}


def test_client_application_onboarding_workout_checkin_coach_review(client, db):
    admin = identity(db, "ADMIN", "Admin")
    coach = identity(db, "COACH", "Coach")
    member = identity(db, "CLIENT", "Member", coach.id)
    admin_headers, coach_headers, member_headers = auth(client, admin), auth(client, coach), auth(client, member)
    lead = client.post("/api/v1/leads", json={"name": "Applicant", "email": "applicant@example.com", "consent": True, "age": 28, "goal": "Strength", "training_experience": "beginner"})
    assert lead.status_code == 201
    listing = client.get("/api/v1/leads", headers=admin_headers).json()["items"]
    assert listing[0]["responses"]["training_experience"] == "beginner"
    assert client.patch(f"/api/v1/leads/{lead.json()['id']}", json={"stage": "QUALIFIED", "notes": "Follow up tomorrow"}, headers=admin_headers).status_code == 200
    profile = client.patch("/api/v1/clients/me/profile", json={"assessment": {"primary_goal": "Strength", "height_cm": 180, "weight_kg": 75, "timezone": "Africa/Kigali"}, "health_screening": {"injury": True}, "consents": [{"kind": kind, "version": "2026-01", "accepted": True} for kind in ["terms", "privacy", "coaching", "liability"]]}, headers=member_headers)
    assert profile.status_code == 200, profile.text
    assert profile.json()["onboarding_complete"] is True
    assert profile.json()["review_required"] is True
    assert db.scalar(select(Consent)).policy_snapshot["version"] == "2026-01"
    exercise = client.post("/api/v1/exercises", json={"name": "Squat", "muscle_group": "Legs", "instructions": "Brace and stand"}, headers=admin_headers).json()
    program = client.post("/api/v1/programs", json={"name": "Foundations", "published": True, "workouts": [{"id": "workout-a", "name": "Day A", "day": 1, "exercises": [{"exercise_id": exercise["id"], "name": "Squat"}]}]}, headers=admin_headers).json()
    assignment = client.post(f"/api/v1/programs/{program['id']}/assign", json={"client_id": member.id}, headers=coach_headers).json()
    session = client.post("/api/v1/workouts/sessions", json={"assignment_id": assignment["id"], "workout_id": "workout-a", "sets": [{"exercise_id": exercise["id"], "set_number": 1, "reps": 10, "weight_kg": 20}], "completed": True}, headers=member_headers)
    assert session.status_code == 201, session.text
    assert client.post("/api/v1/progress", json={"value": 74.5, "kind": "weight", "unit": "kg"}, headers=member_headers).status_code == 201
    checkin = client.post("/api/v1/checkins", json={"answers": {"energy": 4, "sleep": 3, "adherence": 5, "wins": "Trained consistently"}}, headers=member_headers).json()
    reviewed = client.patch(f"/api/v1/checkins/{checkin['id']}", json={"coach_feedback": "Keep the current training load", "status": "REVIEWED"}, headers=coach_headers)
    assert reviewed.status_code == 200
    assert client.post("/api/v1/messages", json={"recipient_id": member.id, "body": "Your check-in is reviewed"}, headers=coach_headers).status_code == 201
    assert client.get("/api/v1/messages", headers=member_headers).json()["total"] == 1
    dashboard = client.get("/api/v1/admin/dashboard", headers=coach_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["metrics"]["total_clients"] == 1
    assert client.get("/api/v1/admin/dashboard", headers=member_headers).status_code == 403


def test_booking_collision_cancel_and_rebooking_preserves_history(client, db):
    coach = identity(db, "COACH", "Coach")
    first = identity(db, name="First", coach_id=coach.id)
    second = identity(db, name="Second", coach_id=coach.id)
    first_headers, second_headers = auth(client, first), auth(client, second)
    slot = client.get("/api/v1/bookings/availability", headers=first_headers).json()["items"][0]
    body = {**{key: slot[key] for key in ["coach_id", "starts_at", "ends_at"]}, "type": "consultation"}
    result = client.post("/api/v1/bookings", json=body, headers=first_headers)
    assert result.status_code == 201, result.text
    assert client.post("/api/v1/bookings", json=body, headers=second_headers).status_code == 409
    assert client.patch(f"/api/v1/bookings/{result.json()['id']}", json={"status": "CANCELLED"}, headers=second_headers).status_code == 403
    assert client.patch(f"/api/v1/bookings/{result.json()['id']}", json={"status": "CANCELLED"}, headers=first_headers).status_code == 200
    second_booking = client.post("/api/v1/bookings", json=body, headers=second_headers)
    assert second_booking.status_code == 201
    assert second_booking.json()["id"] != result.json()["id"]
    first_records = client.get("/api/v1/bookings", headers=first_headers).json()["items"]
    assert first_records[0]["status"] == "CANCELLED"
    assert first_records[0]["client_id"] == first.id


def test_private_media_permissions_type_validation_and_signed_link(client, db, monkeypatch, tmp_path):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "media_root", tmp_path)
    first = identity(db, name="First")
    second = identity(db, name="Second")
    headers = auth(client, first)
    png = BytesIO()
    Image.new("RGB", (2, 2)).save(png, format="PNG")
    png_bytes = png.getvalue()
    bad = client.post("/api/v1/media", files={"file": ("image.jpg", b"<script>bad</script>", "image/jpeg")}, headers=headers)
    assert bad.status_code == 422
    uploaded = client.post("/api/v1/media", files={"file": ("../../photo.png", png_bytes, "image/png")}, data={"purpose": "progress", "public": "false"}, headers=headers)
    assert uploaded.status_code == 201, uploaded.text
    media = uploaded.json()
    assert "storage_key" not in media
    assert client.get(f"/api/v1/media/{media['id']}/file").status_code == 401
    assert client.get(media["url"]).status_code == 200
    assert client.get(f"/api/v1/media/{media['id']}/file", headers=auth(client, second)).status_code == 403
    assert client.post("/api/v1/media", files={"file": ("p.png", png_bytes, "image/png")}, data={"public": "true", "purpose": "marketing"}, headers=headers).status_code == 403


def test_pending_order_cannot_activate_without_server_verification(client, db):
    user = identity(db, name="Member")
    headers = auth(client, user)
    product = Product(name="Monthly", price_minor=10000, currency="USD", billing_interval="monthly", entitlements={"program_access": True})
    db.add(product)
    db.commit()
    order = client.post("/api/v1/orders", json={"product_id": product.id}, headers=headers).json()
    initialize = client.post("/api/v1/payments/initialize", json={"order_id": order["id"]}, headers=headers)
    assert initialize.status_code == 503
    assert db.scalar(select(Subscription)) is None
    assert client.post("/api/v1/payments/webhook", json={"data": {"id": 1}}).status_code == 401
    stored = db.get(Order, order["id"])
    bad = VerifiedPayment("1", stored.reference, 9999, "USD", True)
    import pytest

    from app.core.exceptions import AppError
    with pytest.raises(AppError):
        CommerceService(db).activate(stored, bad)
    assert stored.status == "PENDING"
    assert db.scalar(select(Payment)) is None
    verified = VerifiedPayment("1", stored.reference, 10000, "USD", True)
    result = CommerceService(db).activate(stored, verified)
    assert result["status"] == "PAID"
    assert db.scalar(select(Subscription)).entitlements["program_access"] is True
    assert db.scalar(select(Invoice)).amount_minor == 10000
    assert CommerceService(db).activate(stored, verified)["already_processed"] is True
    assert len(db.scalars(select(Invoice)).all()) == 1
    product.price_minor, product.entitlements = 20000, {"program_access": False}
    db.commit()
    assert stored.snapshot["price_minor"] == 10000
    assert stored.snapshot["entitlements"]["program_access"] is True


def test_live_sessions_require_verified_entitlement_and_limit(client, db):
    coach = identity(db, "COACH", "Coach")
    member = identity(db, name="Member", coach_id=coach.id)
    headers = auth(client, member)
    slots = client.get("/api/v1/bookings/availability", headers=headers).json()["items"]
    body = {**{key: slots[0][key] for key in ["coach_id", "starts_at", "ends_at"]}, "type": "live_training"}
    assert client.post("/api/v1/bookings", json=body, headers=headers).status_code == 403
    product = Product(name="Live Plan", price_minor=10000, currency="USD", entitlements={"live_sessions_per_month": 1})
    db.add(product)
    db.commit()
    order = CommerceService(db).order(product.id, member)
    stored = db.get(Order, order["id"])
    CommerceService(db).activate(stored, VerifiedPayment("202", stored.reference, 10000, "USD", True))
    assert client.post("/api/v1/bookings", json=body, headers=headers).status_code == 201
    next_body = {**{key: slots[1][key] for key in ["coach_id", "starts_at", "ends_at"]}, "type": "live_training"}
    assert client.post("/api/v1/bookings", json=next_body, headers=headers).status_code == 403
