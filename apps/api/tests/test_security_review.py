"""Independent regression coverage for session boundaries found during review."""

import base64
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import access_token
from app.modules.auth.models import RefreshSession, User
from app.modules.clients.models import ClientProfile

ORIGIN = {"Origin": "http://localhost:5173"}


def register(client, email):
    response = client.post("/api/v1/auth/register", json={
        "name": "Security Test", "email": email, "password": "security-review-password",
    }, headers=ORIGIN)
    assert response.status_code == 201, response.text
    return response.json()


def bearer(session):
    return {"Authorization": f"Bearer {session['access_token']}"}


def set_cookies(client, refresh, csrf):
    client.cookies.clear()
    client.cookies.set("sbf_refresh", refresh, path="/api/v1/auth")
    client.cookies.set("sbf_csrf", csrf, path="/")


def test_refresh_requires_origin_and_csrf_from_same_session(client, db):
    register(client, "first@example.com")
    first_refresh = client.cookies.get("sbf_refresh")
    first_csrf = client.cookies.get("sbf_csrf")
    register(client, "second@example.com")
    second_csrf = client.cookies.get("sbf_csrf")

    set_cookies(client, first_refresh, second_csrf)
    mixed = client.post("/api/v1/auth/refresh", headers={**ORIGIN, "X-CSRF-Token": second_csrf})
    assert mixed.status_code == 403
    assert mixed.json()["error"]["code"] == "INVALID_CSRF"
    assert not any(session.revoked for session in db.scalars(select(RefreshSession)).all())

    set_cookies(client, first_refresh, first_csrf)
    assert client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": first_csrf}).status_code == 403
    assert client.post("/api/v1/auth/refresh", headers={**ORIGIN, "X-CSRF-Token": first_csrf}).status_code == 200


def test_refresh_reuse_invalidates_both_old_and_rotated_access_tokens(client):
    original = register(client, "reuse@example.com")
    old_refresh = client.cookies.get("sbf_refresh")
    old_csrf = client.cookies.get("sbf_csrf")
    rotated = client.post("/api/v1/auth/refresh", headers={**ORIGIN, "X-CSRF-Token": old_csrf})
    assert rotated.status_code == 200
    set_cookies(client, old_refresh, old_csrf)
    assert client.post("/api/v1/auth/refresh", headers={**ORIGIN, "X-CSRF-Token": old_csrf}).status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer(original)).status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer(rotated.json())).status_code == 401


def test_logout_all_revokes_only_the_requesting_users_sessions(client, db):
    first = register(client, "logout-first@example.com")
    second = register(client, "logout-second@example.com")
    assert client.post("/api/v1/auth/logout-all", headers=bearer(first)).status_code == 200
    assert client.get("/api/v1/auth/me", headers=bearer(first)).status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer(second)).status_code == 200
    sessions = db.scalars(select(RefreshSession)).all()
    assert all(session.revoked for session in sessions if session.user_id == first["user"]["id"])
    assert all(not session.revoked for session in sessions if session.user_id == second["user"]["id"])


def test_account_deactivation_blocks_existing_access_and_refresh(client, db):
    session = register(client, "deactivate@example.com")
    csrf = client.cookies.get("sbf_csrf")
    user = db.get(User, session["user"]["id"])
    user.active = False
    db.commit()
    assert client.get("/api/v1/auth/me", headers=bearer(session)).status_code == 401
    assert client.post("/api/v1/auth/refresh", headers={**ORIGIN, "X-CSRF-Token": csrf}).status_code == 401


def actor(db, label, role="CLIENT", coach=None):
    user = User(name=label, email=f"{label}@example.com", password_hash="fixture-without-password-login",
                role=role, assigned_coach_id=coach.id if coach else None)
    db.add(user)
    db.flush()
    if role == "CLIENT":
        db.add(ClientProfile(client_id=user.id))
    db.commit()
    return user, {"Authorization": f"Bearer {access_token(user)}"}


def program(client, headers, *, published=False):
    exercise = client.post("/api/v1/exercises", headers=headers, json={
        "name": "Squat", "muscle_group": "Legs", "published": published,
    })
    assert exercise.status_code == 201, exercise.text
    body = {"name": "Original plan", "published": published, "workouts": [{
        "id": "workout-a", "name": "Full body", "day": 1,
        "exercises": [{"exercise_id": exercise.json()["id"], "name": "Squat", "sets": 2, "reps": "10"}],
    }]}
    response = client.post("/api/v1/programs", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json(), body


def test_client_and_unassigned_coach_cannot_read_or_mutate_another_clients_data(client, db):
    coach_a, coach_a_headers = actor(db, "coach-a", "COACH")
    coach_b, coach_b_headers = actor(db, "coach-b", "COACH")
    client_a, headers_a = actor(db, "client-a", coach=coach_a)
    client_b, headers_b = actor(db, "client-b", coach=coach_b)
    template, _ = program(client, coach_b_headers)
    assigned = client.post(f"/api/v1/programs/{template['id']}/assign", headers=coach_b_headers,
                           json={"client_id": client_b.id})
    assert assigned.status_code == 201, assigned.text
    assert client.post("/api/v1/progress", headers=headers_b, json={"value": 75}).status_code == 201
    habit = client.post("/api/v1/habits", headers=coach_b_headers,
                        json={"client_id": client_b.id, "name": "Walk daily"})
    assert habit.status_code == 201, habit.text
    assert client.post("/api/v1/checkins", headers=headers_b,
                       json={"answers": {"energy": 3, "sleep": 3, "adherence": 3}}).status_code == 201
    assert client.post("/api/v1/messages", headers=coach_b_headers,
                       json={"recipient_id": client_b.id, "body": "Private coaching message"}).status_code == 201
    for path in ["progress", "habits", "habits/logs", "checkins", "messages", "programs/assignments", "workouts/sessions"]:
        response = client.get(f"/api/v1/{path}", headers=headers_a)
        assert response.status_code == 200, response.text
        assert response.json()["items"] == [], path
        assert client.get(f"/api/v1/{path}?client_id={client_b.id}", headers=headers_a).status_code == 403
        assert client.get(f"/api/v1/{path}?client_id={client_b.id}", headers=coach_a_headers).status_code == 403
    assert client.get(f"/api/v1/clients/{client_b.id}", headers=headers_a).status_code == 403
    assert client.get(f"/api/v1/nutrition?client_id={client_b.id}", headers=headers_a).status_code == 403
    assert client.patch(f"/api/v1/clients/{client_b.id}/profile", headers=headers_a,
                        json={"assessment": {"primary_goal": "Changed without permission"}}).status_code == 403
    assert client.post("/api/v1/progress", headers=headers_a,
                       json={"client_id": client_b.id, "value": 75}).status_code == 403
    assert client.post(f"/api/v1/habits/{habit.json()['id']}/log", headers=headers_a,
                       json={"date": "2026-01-01", "completed": True}).status_code == 403
    assert client.post("/api/v1/workouts/sessions", headers=headers_a,
                       json={"assignment_id": assigned.json()["id"], "workout_id": "workout-a"}).status_code == 403
    assert client.post("/api/v1/messages", headers=headers_a,
                       json={"recipient_id": client_b.id, "body": "Unauthorized"}).status_code == 403
    assert client.patch("/api/v1/clients/me/profile", headers=headers_a,
                        json={"nutrition_targets": {"calories": 1000}}).status_code == 403
    assert client.get("/api/v1/clients/me/profile", headers=headers_a).json()["client_id"] == client_a.id


def test_assignment_snapshot_survives_template_edits_and_private_exercise_patch_is_denied(client, db):
    owner, owner_headers = actor(db, "owner", "COACH")
    _, other_headers = actor(db, "other", "COACH")
    recipient, recipient_headers = actor(db, "recipient", coach=owner)
    template, body = program(client, owner_headers)
    assigned = client.post(f"/api/v1/programs/{template['id']}/assign", headers=owner_headers,
                           json={"client_id": recipient.id})
    assert assigned.status_code == 201, assigned.text
    before = assigned.json()["snapshot"]
    body["name"] = "Updated template"
    body["workouts"][0]["exercises"][0]["sets"] = 5
    assert client.patch(f"/api/v1/programs/{template['id']}", headers=owner_headers, json=body).status_code == 200
    after = client.get("/api/v1/programs/assignments", headers=recipient_headers).json()["items"][0]["snapshot"]
    assert after == before
    assert after["name"] == "Original plan"
    assert after["workouts"][0]["exercises"][0]["sets"] == 2

    other_template, other_body = program(client, other_headers)
    other_body["workouts"][0]["exercises"][0]["exercise_id"] = body["workouts"][0]["exercises"][0]["exercise_id"]
    assert client.patch(f"/api/v1/programs/{other_template['id']}", headers=other_headers,
                        json=other_body).status_code == 403


def test_consent_is_owner_recorded_current_versioned_and_withdrawal_is_preserved(client, db):
    coach, coach_headers = actor(db, "consent-coach", "COACH")
    user, headers = actor(db, "consent-client", coach=coach)
    required = [{"kind": kind, "version": "2026-01", "accepted": True}
                for kind in ["terms", "privacy", "coaching", "liability"]]
    assert client.patch(f"/api/v1/clients/{user.id}/profile", headers=coach_headers,
                        json={"consents": required}).status_code == 403
    assert client.patch("/api/v1/clients/me/profile", headers=headers, json={
        "consents": [{"kind": "terms", "version": "outdated", "accepted": True}],
    }).status_code == 409
    response = client.patch("/api/v1/clients/me/profile", headers=headers, json={
        "assessment": {"primary_goal": "Build strength"},
        "health_screening": {"heart_condition": True},
        "consents": [*required, {"kind": "photo", "version": "2026-01", "accepted": True}],
    })
    assert response.status_code == 200, response.text
    assert response.json()["onboarding_complete"] is True
    assert response.json()["review_required"] is True
    withdrawal = client.patch("/api/v1/clients/me/profile", headers=headers, json={
        "consents": [{"kind": "photo", "version": "2026-01", "accepted": False}],
    })
    assert withdrawal.status_code == 200, withdrawal.text
    photos = [consent for consent in withdrawal.json()["consents"] if consent["kind"] == "photo"]
    assert [consent["accepted"] for consent in photos] == [True, False]
    assert all(consent["created_at"] for consent in photos)


def test_private_media_requires_authorization_and_signed_tokens_are_bound_to_asset(client, db, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "media_root", tmp_path)
    _, owner_headers = actor(db, "media-owner")
    _, other_headers = actor(db, "media-other")
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC")
    response = client.post("/api/v1/media", headers=owner_headers,
                           files={"file": ("progress.png", png, "image/png")},
                           data={"purpose": "progress", "caption": "Private progress", "public": "false"})
    assert response.status_code == 201, response.text
    first = response.json()
    assert first["public"] is False
    assert "storage_key" not in first
    assert client.get(f"/api/v1/media/{first['id']}/file").status_code == 401
    assert client.get(f"/api/v1/media/{first['id']}/file", headers=other_headers).status_code == 403
    assert client.get(first["url"]).content == png
    assert client.get("/api/v1/media", headers=other_headers).json()["items"] == []

    second = client.post("/api/v1/media", headers=other_headers,
                         files={"file": ("other.png", png, "image/png")}, data={"purpose": "progress"})
    assert second.status_code == 201, second.text
    token = parse_qs(urlparse(first["url"]).query)["token"][0]
    assert client.get(f"/api/v1/media/{second.json()['id']}/file", params={"token": token}).status_code == 403
    assert client.delete(f"/api/v1/media/{first['id']}", headers=owner_headers).status_code == 200
    assert client.get(first["url"]).status_code == 404


def test_public_transformations_disappear_when_separate_photo_consent_is_withdrawn(client, db):
    _, admin_headers = actor(db, "publication-admin", "ADMIN")
    user, user_headers = actor(db, "publication-client")
    story = {"client_id": user.id, "alias": "Client story", "consent_status": "GRANTED",
             "before_image_url": "https://example.com/before.jpg", "after_image_url": "https://example.com/after.jpg"}
    assert client.patch("/api/v1/settings", headers=admin_headers, json={"transformations": [story]}).status_code == 422
    assert client.patch("/api/v1/clients/me/profile", headers=user_headers, json={
        "consents": [{"kind": "photo", "version": "2026-01", "accepted": True}],
    }).status_code == 200
    assert client.patch("/api/v1/settings", headers=admin_headers, json={"transformations": [story]}).status_code == 200
    assert len(client.get("/api/v1/content/public").json()["transformations"]) == 1
    assert client.patch("/api/v1/clients/me/profile", headers=user_headers, json={
        "consents": [{"kind": "photo", "version": "2026-01", "accepted": False}],
    }).status_code == 200
    assert client.get("/api/v1/content/public").json()["transformations"] == []
