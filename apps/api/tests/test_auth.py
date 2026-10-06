from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.security import hash_password, token_hash
from app.modules.auth.models import ActionToken, RefreshSession, User

ORIGIN = {"Origin": "http://localhost:5173"}


def signup(client, email="person@example.com"):
    result = client.post("/api/v1/auth/register", json={"name": "Test Person", "email": email, "password": "long-strong-password"}, headers=ORIGIN)
    assert result.status_code == 201, result.text
    return result.json()


def test_registration_is_client_and_hashes_password(client, db):
    result = signup(client)
    user = db.get(User, result["user"]["id"])
    assert user.password_hash.startswith("$argon2id$")
    assert user.role == "CLIENT"
    assert "password_hash" not in result["user"]
    privileged = client.post("/api/v1/auth/register", json={"name": "Other", "email": "other@example.com", "password": "long-strong-password", "role": "ADMIN"})
    assert privileged.status_code == 422
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {result['access_token']}"}).status_code == 200


def test_refresh_rotates_and_reuse_revokes_family(client, db):
    signup(client)
    old_refresh = client.cookies.get("sbf_refresh")
    old_csrf = client.cookies.get("sbf_csrf")
    assert client.post("/api/v1/auth/refresh", headers=ORIGIN).status_code == 403
    headers = {**ORIGIN, "X-CSRF-Token": old_csrf}
    assert client.post("/api/v1/auth/refresh", headers=headers).status_code == 200
    assert client.cookies.get("sbf_refresh") != old_refresh
    assert len(db.scalars(select(RefreshSession)).all()) == 2
    client.cookies.clear()
    client.cookies.set("sbf_refresh", old_refresh, path="/api/v1/auth")
    client.cookies.set("sbf_csrf", old_csrf)
    assert client.post("/api/v1/auth/refresh", headers=headers).status_code == 401
    assert all(session.revoked for session in db.scalars(select(RefreshSession)).all())


def test_invalid_origin_denied_and_reset_revokes_access(client, db):
    result = signup(client)
    csrf = client.cookies.get("sbf_csrf")
    assert client.post("/api/v1/auth/refresh", headers={"Origin": "https://evil.example", "X-CSRF-Token": csrf}).status_code == 403
    raw = "reset-token-for-test-only-very-long"
    db.add(ActionToken(user_id=result["user"]["id"], token_hash=token_hash(raw), purpose="reset", expires_at=datetime.now(UTC) + timedelta(minutes=10)))
    db.commit()
    assert client.post("/api/v1/auth/reset-password", json={"token": raw, "password": "new-strong-password"}).status_code == 200
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {result['access_token']}"}).status_code == 401
    assert client.post("/api/v1/auth/reset-password", json={"token": raw, "password": "new-strong-password"}).status_code == 400


def test_seed_local_email_can_login(client, db):
    db.add(User(name="Local admin", email="admin@syrebanksfitness.local", password_hash=hash_password("long-strong-password"), role="ADMIN"))
    db.commit()
    assert client.post("/api/v1/auth/login", json={"email": "admin@syrebanksfitness.local", "password": "long-strong-password"}).status_code == 200


def test_account_deactivation_revokes_login_and_tokens(client):
    result = signup(client)
    headers = {"Authorization": f"Bearer {result['access_token']}"}
    assert client.post("/api/v1/auth/deactivate", json={"password": "incorrect-password"}, headers=headers).status_code == 401
    assert client.post("/api/v1/auth/deactivate", json={"password": "long-strong-password"}, headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": result["user"]["email"], "password": "long-strong-password"}).status_code == 401
