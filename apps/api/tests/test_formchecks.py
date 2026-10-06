from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import access_token
from app.modules.admin.models import AuditLog
from app.modules.auth.models import User
from app.modules.cms.models import MediaAsset
from app.modules.coaching.models import Exercise, Program, ProgramAssignment
from app.modules.experience.models import Notification
from app.modules.formchecks.models import FormCheck


@pytest.fixture
def setup(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "storage_provider", "local")
    admin = User(name="Administrator", email="form-admin@example.com", role="ADMIN", password_hash="fixture")
    coach = User(name="Assigned coach", email="form-coach@example.com", role="COACH", password_hash="fixture")
    stranger = User(name="Other coach", email="form-stranger@example.com", role="COACH", password_hash="fixture")
    db.add_all([admin, coach, stranger])
    db.flush()
    owner = User(name="Video owner", email="form-owner@example.com", role="CLIENT", password_hash="fixture", assigned_coach_id=coach.id)
    other = User(name="Other client", email="form-other@example.com", role="CLIENT", password_hash="fixture", assigned_coach_id=stranger.id)
    db.add_all([owner, other])
    db.flush()
    exercise = Exercise(name="Squat", muscle_group="Legs", owner_id=coach.id, published=True)
    assigned_exercise = Exercise(name="Assigned movement", muscle_group="Legs", owner_id=coach.id, published=False)
    forbidden_exercise = Exercise(name="Private other movement", muscle_group="Legs", owner_id=stranger.id, published=False)
    db.add_all([exercise, assigned_exercise, forbidden_exercise])
    db.flush()
    template = Program(name="Assigned plan", owner_id=coach.id, workouts=[])
    db.add(template)
    db.flush()
    db.add(ProgramAssignment(client_id=owner.id, program_id=template.id, assigned_by=coach.id, snapshot={
        "workouts": [{"exercises": [{"exercise_id": assigned_exercise.id}]}],
    }))

    def media(user, public=False, kind="video/mp4", purpose="private"):
        asset = MediaAsset(owner_id=user.id, storage_key=f"{uuid4()}.mp4", content_type=kind,
                           size=1024, public=public, purpose=purpose)
        db.add(asset)
        db.flush()
        return asset

    videos = {"valid": media(owner), "other": media(other), "public": media(owner, public=True),
              "image": media(owner, kind="image/png"), "archived": media(owner, purpose="archived")}
    db.commit()
    users = {"admin": admin, "coach": coach, "stranger": stranger, "owner": owner, "other": other}
    headers = {name: {"Authorization": f"Bearer {access_token(user)}"} for name, user in users.items()}
    return {"users": users, "headers": headers, "videos": videos,
            "exercise": exercise, "assigned_exercise": assigned_exercise, "forbidden_exercise": forbidden_exercise}


def submit(client, setup, *, media="valid", exercise="exercise", actor="owner"):
    return client.post("/api/v1/formchecks", headers=setup["headers"][actor], json={
        "exercise_id": setup[exercise].id, "media_asset_id": setup["videos"][media].id,
        "comment": "Please check the last repetition.",
    })


def test_private_video_submission_review_feedback_and_audit(client, db, setup):
    response = submit(client, setup)
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["client_id"] == setup["users"]["owner"].id
    assert record["status"] == "SUBMITTED"
    assert record["exercise_name"] == "Squat"
    assert record["media_available"] is True
    assert "?token=" in record["media_url"]
    assert "storage_key" not in record
    notified = {notification.user_id for notification in db.scalars(select(Notification)).all()}
    assert notified == {setup["users"]["admin"].id, setup["users"]["coach"].id}

    for actor in ["other", "stranger"]:
        own_list = client.get("/api/v1/formchecks", headers=setup["headers"][actor])
        assert own_list.status_code == 200
        assert own_list.json()["items"] == []
        assert client.get("/api/v1/formchecks", headers=setup["headers"][actor],
                          params={"client_id": setup["users"]["owner"].id}).status_code == 403
    review = {"status": "NEEDS_CORRECTION", "feedback": "Keep your knees tracking with your toes.",
              "timestamped_notes": [{"seconds": 3.5, "note": "Slow the lowering phase here."}]}
    for actor in ["owner", "other", "stranger"]:
        denied = client.patch(f"/api/v1/formchecks/{record['id']}", headers=setup["headers"][actor], json=review)
        assert denied.status_code == 403
    result = client.patch(f"/api/v1/formchecks/{record['id']}", headers=setup["headers"]["coach"], json=review)
    assert result.status_code == 200, result.text
    assert result.json()["reviewed_by"] == setup["users"]["coach"].id
    assert result.json()["reviewed_at"]
    assert result.json()["timestamped_notes"] == review["timestamped_notes"]
    assert db.get(FormCheck, record["id"]).status == "NEEDS_CORRECTION"
    assert setup["users"]["owner"].id in {n.user_id for n in db.scalars(select(Notification)).all()}
    actions = [log.action for log in db.scalars(select(AuditLog)).all()]
    assert actions.count("formcheck.submitted") == 1
    assert actions.count("formcheck.reviewed") == 1


@pytest.mark.parametrize(("media", "status"), [("other", 403), ("public", 422), ("image", 422), ("archived", 422)])
def test_submission_rejects_another_clients_public_or_nonvideo_assets(client, setup, media, status):
    assert submit(client, setup, media=media).status_code == status


def test_only_client_and_authorized_exercises_can_be_submitted(client, setup):
    assert submit(client, setup, actor="coach").status_code == 403
    assert submit(client, setup, exercise="forbidden_exercise").status_code == 403
    assert submit(client, setup, exercise="assigned_exercise").status_code == 201
    assert submit(client, setup).status_code == 409


@pytest.mark.parametrize("seconds", [-1, "NaN", "Infinity", 3601])
def test_review_rejects_invalid_video_timestamps(client, setup, seconds):
    record = submit(client, setup).json()
    response = client.patch(f"/api/v1/formchecks/{record['id']}", headers=setup["headers"]["coach"], json={
        "status": "REVIEWED", "feedback": "Focus on controlled movement.",
        "timestamped_notes": [{"seconds": seconds, "note": "Check this point."}],
    })
    assert response.status_code == 422


def test_archival_or_privacy_change_removes_video_link_but_preserves_feedback(client, db, setup):
    record = submit(client, setup).json()
    video = setup["videos"]["valid"]
    video.purpose = "archived"
    db.commit()
    response = client.get("/api/v1/formchecks", headers=setup["headers"]["owner"])
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["id"] == record["id"]
    assert item["media_available"] is False
    assert item["media_url"] is None


def test_mp4_upload_then_submission_and_admin_approval(client, setup, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "media_root", tmp_path)
    # The upload gate checks container MIME/signature, not video transcoding.
    content = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
    uploaded = client.post("/api/v1/media", headers=setup["headers"]["owner"],
                           files={"file": ("movement.mp4", content, "video/mp4")},
                           data={"purpose": "private", "public": "false", "caption": "Private form review"})
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["public"] is False
    result = client.post("/api/v1/formchecks", headers=setup["headers"]["owner"], json={
        "exercise_id": setup["exercise"].id, "media_asset_id": uploaded.json()["id"], "comment": "Check my tempo.",
    })
    assert result.status_code == 201, result.text
    playback = client.get(result.json()["media_url"])
    assert playback.status_code == 200
    assert playback.headers["content-type"] == "video/mp4"
    assert playback.content == content
    approved = client.patch(f"/api/v1/formchecks/{result.json()['id']}", headers=setup["headers"]["admin"], json={
        "status": "APPROVED", "feedback": "Your tempo is controlled. Keep practicing.", "timestamped_notes": [],
    })
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
