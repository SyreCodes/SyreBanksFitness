import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.security import access_token
from app.modules.admin.models import AuditLog
from app.modules.feedback.models import FeedbackVote
from tests.test_core_loop import identity

POST = {"title": "Make rest timers easier to find", "description": "A visible rest timer would help me stay focused between sets.", "category": "feature"}


def headers(user):
    return {"Authorization": f"Bearer {access_token(user)}"}


def create(client, user, **changes):
    result = client.post("/api/v1/feedback", headers=headers(user), json={**POST, **changes})
    assert result.status_code == 201, result.text
    return result.json()


def test_feedback_requires_client_or_staff_identity(client, db):
    assert client.get("/api/v1/feedback").status_code == 401
    assert client.post("/api/v1/feedback", json=POST).status_code == 401
    lead = identity(db, "LEAD", "Applicant")
    member = identity(db, name="Member")
    post = create(client, member)
    for response in [client.get("/api/v1/feedback", headers=headers(lead)), client.post("/api/v1/feedback", json=POST, headers=headers(lead)), client.post(f"/api/v1/feedback/{post['id']}/vote", json={"voted": True}, headers=headers(lead)), client.patch(f"/api/v1/feedback/{post['id']}", json={"status": "PLANNED"}, headers=headers(lead))]:
        assert response.status_code == 403
    assert client.post(f"/api/v1/feedback/{post['id']}/vote", json={"voted": True}).status_code == 401
    assert client.patch(f"/api/v1/feedback/{post['id']}", json={"status": "PLANNED"}).status_code == 401


def test_votes_are_unique_and_desired_state_retries_are_idempotent(client, db):
    first = identity(db, name="First")
    second = identity(db, name="Second")
    post = create(client, first)
    url = f"/api/v1/feedback/{post['id']}/vote"
    for _ in range(2):
        voted = client.post(url, json={"voted": True}, headers=headers(first))
        assert voted.status_code == 200, voted.text
        assert voted.json()["vote_count"] == 1 and voted.json()["voted"] is True
    assert db.scalar(select(func.count()).select_from(FeedbackVote)) == 1
    db.add(FeedbackVote(post_id=post["id"], user_id=first.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert client.post(url, json={"voted": True}, headers=headers(second)).json()["vote_count"] == 2
    for _ in range(2):
        result = client.post(url, json={"voted": False}, headers=headers(first)).json()
        assert result["vote_count"] == 1 and result["voted"] is False
    assert db.scalar(select(func.count()).select_from(FeedbackVote)) == 1
    actions = db.scalars(select(AuditLog.action).where(AuditLog.resource_id == post["id"])).all()
    assert actions.count("feedback.voted") == 2
    assert actions.count("feedback.vote_removed") == 1


def test_only_admin_can_review_and_no_private_account_fields_are_published(client, db):
    member = identity(db, name="Aline PrivateSurname")
    coach = identity(db, "COACH", "Coach")
    admin = identity(db, "ADMIN", "Admin")
    post = create(client, member)
    assert post["owner_name"] == "Aline" and post["own_post"] is True
    url = f"/api/v1/feedback/{post['id']}"
    patch = {"status": "PLANNED", "coach_response": "We’re exploring a clearer workout timer."}
    assert client.patch(url, json=patch, headers=headers(member)).status_code == 403
    assert client.patch(url, json=patch, headers=headers(coach)).status_code == 403
    updated = client.patch(url, json=patch, headers=headers(admin))
    assert updated.status_code == 200, updated.text
    output = client.get("/api/v1/feedback", headers=headers(coach)).json()["items"][0]
    assert output["status"] == "PLANNED" and output["coach_response"] == patch["coach_response"]
    assert output["own_post"] is False
    assert {"owner_id", "email", "password_hash", "private_notes", "internal_comments"}.isdisjoint(output)
    assert "PrivateSurname" not in str(output) and member.email not in str(output)
    assert client.patch(url, json={"internal_comments": "Private admin content"}, headers=headers(admin)).status_code == 422
    assert db.scalar(select(AuditLog).where(AuditLog.resource_id == post["id"], AuditLog.action == "feedback.reviewed"))


def test_feedback_validation_filtering_and_pagination(client, db):
    member = identity(db, name="Member")
    admin = identity(db, "ADMIN", "Admin")
    create(client, member)
    create(client, member, title="Useful workout instructions", category="compliment", description="The written movement instructions help me train confidently.")
    result = client.get("/api/v1/feedback?category=feature&search=timer&limit=1", headers=headers(member))
    assert result.status_code == 200 and result.json()["total"] == 1
    assert len(result.json()["items"]) == 1
    assert client.get("/api/v1/feedback?offset=2", headers=headers(member)).json()["items"] == []
    assert client.get("/api/v1/feedback?category=private", headers=headers(member)).status_code == 422
    assert client.post("/api/v1/feedback", json={**POST, "title": "  "}, headers=headers(member)).status_code == 422
    assert client.post("/api/v1/feedback", json={**POST, "status": "COMPLETED"}, headers=headers(member)).status_code == 422
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.post(f"/api/v1/feedback/{missing}/vote", json={"voted": True}, headers=headers(member)).status_code == 404
    assert client.post(f"/api/v1/feedback/{missing}/vote", json={"voted": "yes"}, headers=headers(member)).status_code == 422
    assert client.patch(f"/api/v1/feedback/{missing}", json={"status": "PLANNED"}, headers=headers(admin)).status_code == 404
    assert client.patch(f"/api/v1/feedback/{missing}", json={"status": None}, headers=headers(admin)).status_code == 422
