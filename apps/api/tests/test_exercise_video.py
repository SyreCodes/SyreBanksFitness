import asyncio
from pathlib import Path
from tempfile import SpooledTemporaryFile

import pytest
from fastapi import UploadFile
from sqlalchemy import select
from starlette.datastructures import Headers

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import access_token
from app.modules.admin.models import AuditLog
from app.modules.auth.models import User
from app.modules.cms.models import MediaAsset
from app.modules.cms.routes import file_download
from app.modules.coaching.models import Exercise
from app.modules.coaching.schemas import ExerciseCreate
from app.modules.coaching.services import CoachingService
from app.modules.coaching.video import upload_policy
from app.providers.storage import LocalStorage

MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
WEBM = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01webm\x00\x00"
MOV = b"\x00\x00\x00\x18ftypqt  \x00\x00\x00\x00qt  "


@pytest.fixture
def actors(db, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "storage_provider", "local")
    monkeypatch.setattr(get_settings(), "media_root", tmp_path)
    users = {}
    for role, label in [("COACH", "owner"), ("COACH", "other"), ("ADMIN", "admin"), ("CLIENT", "client")]:
        user = User(name=label, email=f"exercise-{label}@example.com", role=role, password_hash="fixture")
        db.add(user)
        db.flush()
        users[label] = user
    db.commit()
    return {label: {"Authorization": f"Bearer {access_token(user)}"} for label, user in users.items()}, users, tmp_path


def exercise(client, headers, *, published=True, media_url=None):
    body = {"name": "Squat", "muscle_group": "Legs", "published": published, "media_url": media_url}
    result = client.post("/api/v1/exercises", json=body, headers=headers)
    assert result.status_code == 201, result.text
    return result.json(), body


def upload(client, exercise_id, headers, content=MP4, content_type="video/mp4", key=None):
    upload_headers = {**headers, **({"Idempotency-Key": key} if key else {})}
    return client.post(f"/api/v1/exercises/{exercise_id}/video", headers=upload_headers,
                       files={"file": ("demonstration.mp4", content, content_type)})


def in_memory_upload(content=MP4, content_type="video/mp4"):
    file = SpooledTemporaryFile(max_size=len(content) + 1)
    file.write(content)
    file.seek(0)
    return UploadFile(file=file, filename="demonstration.mp4", headers=Headers({"content-type": content_type}))


def test_service_video_lifecycle_and_permissions(db, actors):
    _, users, root = actors
    service = CoachingService(db)
    record = service.create_exercise(ExerciseCreate(name="Squat", muscle_group="Legs", published=False), users["owner"])
    with pytest.raises(AppError) as denied:
        asyncio.run(service.upload_exercise_video(record["id"], in_memory_upload(), users["other"]))
    assert denied.value.status == 403

    private = asyncio.run(service.upload_exercise_video(record["id"], in_memory_upload(), users["admin"]))
    asset = db.get(MediaAsset, private["video_media_id"])
    assert asset.owner_id == users["owner"].id and asset.public is False
    assert "?token=" in private["video_url"]
    assert (root / asset.storage_key).read_bytes() == MP4
    with pytest.raises(AppError) as forbidden:
        file_download(asset.id, db, None)
    assert forbidden.value.status == 401

    published = service.patch_exercise(record["id"], ExerciseCreate(name="Squat", muscle_group="Legs"), users["owner"])
    assert published["video_url"] == f"/api/v1/media/{asset.id}/file"
    assert asset.public is True
    assert file_download(asset.id, db, None).path == root / asset.storage_key

    replaced = asyncio.run(service.upload_exercise_video(record["id"], in_memory_upload(MP4 + b"new"), users["owner"]))
    assert replaced["video_media_id"] != asset.id and asset.purpose == "archived"
    assert not (root / asset.storage_key).exists()
    external = service.patch_exercise(record["id"], ExerciseCreate(
        name="Squat", muscle_group="Legs", media_url="https://example.com/squat.mp4"), users["owner"])
    assert external["video_media_id"] is None and external["video_url"] == "https://example.com/squat.mp4"
    latest = asyncio.run(service.upload_exercise_video(record["id"], in_memory_upload(), users["owner"]))
    assert latest["media_url"] is None
    removed = service.delete_exercise_video(record["id"], users["owner"])
    assert removed["video_media_id"] is None and removed["video_url"] is None
    assert db.get(MediaAsset, latest["video_media_id"]).purpose == "archived"


def test_service_rejects_invalid_mp4_without_storage_or_asset(db, actors):
    _, users, root = actors
    service = CoachingService(db)
    record = service.create_exercise(ExerciseCreate(name="Squat", muscle_group="Legs"), users["owner"])
    with pytest.raises(AppError) as invalid:
        asyncio.run(service.upload_exercise_video(record["id"], in_memory_upload(b"fake video"), users["owner"]))
    assert invalid.value.status == 422
    assert db.scalars(select(MediaAsset)).all() == []
    assert list(root.iterdir()) == []


def test_service_video_policy_types_and_size(db, actors, monkeypatch):
    _, users, _ = actors
    service = CoachingService(db)
    record = service.create_exercise(ExerciseCreate(name="Squat", muscle_group="Legs"), users["owner"])
    assert upload_policy() == {"max_bytes": get_settings().video_max_upload_bytes,
                               "accepted_types": ["video/mp4", "video/webm", "video/quicktime"]}
    for content, content_type in ((WEBM, "video/webm"), (MOV, "video/quicktime")):
        item = asyncio.run(service.upload_exercise_video(record["id"], in_memory_upload(content, content_type), users["owner"]))
        assert db.get(MediaAsset, item["video_media_id"]).content_type == content_type
        assert item["video_url"] == f"/api/v1/media/{item['video_media_id']}/file"

    previous_id = db.get(Exercise, record["id"]).video_media_id
    monkeypatch.setattr(get_settings(), "video_max_upload_mb", 1)
    with pytest.raises(AppError) as oversized:
        asyncio.run(service.upload_exercise_video(record["id"], in_memory_upload(MP4 + b"x" * (1024 * 1024)), users["owner"]))
    assert oversized.value.status == 413 and oversized.value.code == "UPLOAD_TOO_LARGE"
    assert db.get(Exercise, record["id"]).video_media_id == previous_id


def test_service_idempotent_retries_and_stale_uploads(db, actors):
    _, users, _ = actors
    service = CoachingService(db)
    record = service.create_exercise(ExerciseCreate(name="Squat", muscle_group="Legs"), users["owner"])
    key = "exercise-upload-12345678"
    first = asyncio.run(service.upload_exercise_video(record["id"], in_memory_upload(), users["owner"], key))
    again = asyncio.run(service.upload_exercise_video(record["id"], in_memory_upload(), users["owner"], key))
    assert again["video_media_id"] == first["video_media_id"]
    assert len(db.scalars(select(MediaAsset)).all()) == 1
    with pytest.raises(AppError) as reused:
        asyncio.run(service.upload_exercise_video(record["id"], in_memory_upload(MP4 + b"different"), users["owner"], key))
    assert reused.value.code == "IDEMPOTENCY_CONFLICT"
    replacement = asyncio.run(service.upload_exercise_video(record["id"], in_memory_upload(MP4 + b"new"),
                                                               users["owner"], "exercise-upload-87654321"))
    with pytest.raises(AppError) as stale:
        asyncio.run(service.upload_exercise_video(record["id"], in_memory_upload(), users["owner"], key))
    assert stale.value.code == "IDEMPOTENCY_CONFLICT"
    assert db.get(Exercise, record["id"]).video_media_id == replacement["video_media_id"]


def test_service_storage_failure_preserves_previous_file(db, actors, monkeypatch, caplog):
    _, users, root = actors
    service = CoachingService(db)
    record = service.create_exercise(ExerciseCreate(name="Squat", muscle_group="Legs"), users["owner"])
    first = asyncio.run(service.upload_exercise_video(record["id"], in_memory_upload(), users["owner"]))
    asset = db.get(MediaAsset, first["video_media_id"])

    original_save = LocalStorage.save_file

    def fail_storage(*_args):
        raise PermissionError("read-only media directory")

    monkeypatch.setattr(LocalStorage, "save_file", fail_storage)
    with pytest.raises(AppError) as unavailable:
        asyncio.run(service.upload_exercise_video(record["id"], in_memory_upload(MP4 + b"new"),
                                                   users["owner"], "failed-upload-12345678"))
    assert unavailable.value.status == 503 and unavailable.value.code == "STORAGE_UNAVAILABLE"
    assert db.get(Exercise, record["id"]).video_media_id == asset.id
    assert (root / asset.storage_key).read_bytes() == MP4
    assert len(db.scalars(select(MediaAsset)).all()) == 1
    assert any(getattr(row, "error_category", None) == "STORAGE_UNAVAILABLE"
               and getattr(row, "error_type", None) == "PermissionError" for row in caplog.records)

    monkeypatch.setattr(LocalStorage, "save_file", original_save)
    recovered = asyncio.run(service.upload_exercise_video(record["id"], in_memory_upload(MP4 + b"new"),
                                                          users["owner"], "failed-upload-12345678"))
    assert recovered["video_media_id"] != asset.id
    assert db.get(Exercise, record["id"]).video_media_id == recovered["video_media_id"]
    assert len(db.scalars(select(MediaAsset)).all()) == 2


def test_published_video_upload_playback_and_permissions(client, db, actors):
    headers, users, root = actors
    record, _ = exercise(client, headers["owner"])
    path = f"/api/v1/exercises/{record['id']}/video"
    assert client.post(path, files={"file": ("video.mp4", MP4, "video/mp4")}).status_code == 401
    assert upload(client, record["id"], headers["client"]).status_code == 403
    assert upload(client, record["id"], headers["other"]).status_code == 403

    result = upload(client, record["id"], headers["owner"])
    assert result.status_code == 200, result.text
    uploaded = result.json()
    assert uploaded["video_media_id"]
    assert uploaded["video_url"] == f"/api/v1/media/{uploaded['video_media_id']}/file"
    assert uploaded["media_url"] is None
    asset = db.get(MediaAsset, uploaded["video_media_id"])
    assert asset.owner_id == users["owner"].id
    assert asset.purpose == "exercise" and asset.public is True and asset.content_type == "video/mp4"
    assert (root / asset.storage_key).read_bytes() == MP4
    assert client.get(uploaded["video_url"]).content == MP4
    public = client.get("/api/v1/exercises").json()["items"]
    assert public[0]["video_url"] == uploaded["video_url"]
    actions = [row.action for row in db.scalars(select(AuditLog)).all()]
    assert "media.uploaded" in actions and "exercise.video_uploaded" in actions


def test_unpublished_video_stays_private_until_publication(client, db, actors):
    headers, users, _ = actors
    record, body = exercise(client, headers["owner"], published=False)
    response = upload(client, record["id"], headers["admin"])
    assert response.status_code == 200, response.text
    item = response.json()
    asset = db.get(MediaAsset, item["video_media_id"])
    assert asset.owner_id == users["owner"].id and asset.public is False
    path = f"/api/v1/media/{asset.id}/file"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=headers["other"]).status_code == 404
    assert client.get(item["video_url"]).content == MP4
    assert client.get("/api/v1/exercises").json()["items"] == []
    owner_item = client.get("/api/v1/exercises", headers=headers["owner"]).json()["items"][0]
    assert "?token=" in owner_item["video_url"]

    body["published"] = True
    published = client.patch(f"/api/v1/exercises/{record['id']}", json=body, headers=headers["owner"])
    assert published.status_code == 200, published.text
    assert published.json()["video_url"] == path
    assert asset.public is True
    assert client.get(path).content == MP4

    body["published"] = False
    hidden = client.patch(f"/api/v1/exercises/{record['id']}", json=body, headers=headers["owner"])
    assert hidden.status_code == 200, hidden.text
    assert asset.public is False
    assert client.get(path).status_code == 401


def test_replacement_external_switch_and_remove_archive_old_files(client, db, actors):
    headers, _, root = actors
    record, body = exercise(client, headers["owner"])
    first = upload(client, record["id"], headers["owner"]).json()
    old_asset = db.get(MediaAsset, first["video_media_id"])
    old_path = Path(root / old_asset.storage_key)
    second = upload(client, record["id"], headers["owner"], content=MP4 + b"second")
    assert second.status_code == 200, second.text
    assert second.json()["video_media_id"] != first["video_media_id"]
    assert old_asset.purpose == "archived" and old_asset.public is False
    assert not old_path.exists()
    assert client.get(first["video_url"]).status_code == 404

    body["media_url"] = "https://example.com/squat-demo.mp4"
    external = client.patch(f"/api/v1/exercises/{record['id']}", json=body, headers=headers["owner"])
    assert external.status_code == 200, external.text
    assert external.json()["video_media_id"] is None
    assert external.json()["video_url"] == body["media_url"]
    replaced_asset = db.get(MediaAsset, second.json()["video_media_id"])
    assert replaced_asset.purpose == "archived"
    assert not (root / replaced_asset.storage_key).exists()

    third = upload(client, record["id"], headers["owner"])
    assert third.status_code == 200
    assert third.json()["media_url"] is None
    last_asset = db.get(MediaAsset, third.json()["video_media_id"])
    removed = client.delete(f"/api/v1/exercises/{record['id']}/video", headers=headers["owner"])
    assert removed.status_code == 200
    assert removed.json()["video_url"] is None
    assert removed.json()["video_media_id"] is None
    assert last_asset.purpose == "archived" and not (root / last_asset.storage_key).exists()
    assert client.get(third.json()["video_url"]).status_code == 404


def test_invalid_or_oversize_video_creates_no_asset(client, db, actors, monkeypatch):
    headers, _, root = actors
    record, _ = exercise(client, headers["owner"])
    assert upload(client, record["id"], headers["owner"], b"<script>bad</script>").status_code == 422
    assert upload(client, record["id"], headers["owner"], MP4, "image/png").status_code == 422
    monkeypatch.setattr(get_settings(), "video_max_upload_mb", 1)
    oversize = upload(client, record["id"], headers["owner"], MP4 + b"x" * (1024 * 1024))
    assert oversize.status_code == 413
    assert oversize.json()["error"]["code"] == "UPLOAD_TOO_LARGE"
    assert oversize.json()["error"]["details"]["max_bytes"] == 1024 * 1024
    assert db.scalars(select(MediaAsset)).all() == []
    assert list(root.iterdir()) == []
    assert db.get(Exercise, record["id"]).video_media_id is None


def test_video_policy_and_supported_containers(client, db, actors):
    headers, _, _ = actors
    policy = client.get("/api/v1/exercises/video-upload-policy")
    assert policy.status_code == 200
    assert policy.json() == {"max_bytes": get_settings().video_max_upload_bytes,
                             "accepted_types": ["video/mp4", "video/webm", "video/quicktime"]}
    preflight = client.options("/api/v1/exercises/example/video", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,idempotency-key",
    })
    assert preflight.status_code == 200
    assert "idempotency-key" in preflight.headers["access-control-allow-headers"].lower()
    record, _ = exercise(client, headers["owner"])
    webm = upload(client, record["id"], headers["owner"], WEBM, "video/webm")
    assert webm.status_code == 200, webm.text
    assert db.get(MediaAsset, webm.json()["video_media_id"]).content_type == "video/webm"
    mov = upload(client, record["id"], headers["owner"], MOV, "video/quicktime")
    assert mov.status_code == 200, mov.text
    assert db.get(MediaAsset, mov.json()["video_media_id"]).content_type == "video/quicktime"
    assert client.get(mov.json()["video_url"]).content == MOV


def test_idempotent_retry_does_not_duplicate_or_revert_video(client, db, actors):
    headers, _, _ = actors
    record, _ = exercise(client, headers["owner"])
    upload_id = "exercise-upload-12345678"
    first = upload(client, record["id"], headers["owner"], key=upload_id)
    assert first.status_code == 200, first.text
    same = upload(client, record["id"], headers["owner"], key=upload_id)
    assert same.status_code == 200, same.text
    assert same.json()["video_media_id"] == first.json()["video_media_id"]
    assert len(db.scalars(select(MediaAsset)).all()) == 1
    mismatch = upload(client, record["id"], headers["owner"], MP4 + b"different", key=upload_id)
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    second = upload(client, record["id"], headers["owner"], MP4 + b"replacement", key="exercise-upload-87654321")
    assert second.status_code == 200, second.text
    assert second.json()["video_media_id"] != first.json()["video_media_id"]
    stale = upload(client, record["id"], headers["owner"], key=upload_id)
    assert stale.status_code == 409
    assert db.get(Exercise, record["id"]).video_media_id == second.json()["video_media_id"]


def test_storage_failure_explains_error_and_preserves_video(client, db, actors, monkeypatch, caplog):
    headers, _, root = actors
    record, _ = exercise(client, headers["owner"])
    first = upload(client, record["id"], headers["owner"])
    assert first.status_code == 200, first.text
    original_asset = db.get(MediaAsset, first.json()["video_media_id"])
    original_path = root / original_asset.storage_key

    def fail_storage(*_args):
        raise PermissionError("read-only media directory")

    monkeypatch.setattr(LocalStorage, "save_file", fail_storage)
    replacement = upload(client, record["id"], headers["owner"], MP4 + b"replacement", key="failed-upload-12345678")
    assert replacement.status_code == 503, replacement.text
    assert replacement.json()["error"]["code"] == "STORAGE_UNAVAILABLE"
    assert "temporarily unavailable" in replacement.json()["error"]["message"]
    assert db.get(Exercise, record["id"]).video_media_id == original_asset.id
    assert original_asset.purpose == "exercise" and original_path.read_bytes() == MP4
    assert len(db.scalars(select(MediaAsset)).all()) == 1
    events = [row for row in caplog.records if row.getMessage() == "exercise_video_upload"]
    assert any(getattr(row, "error_category", None) == "STORAGE_UNAVAILABLE" for row in events)


def test_invalid_exercise_does_not_store_video(client, db, actors):
    headers, _, root = actors
    result = upload(client, "not-a-real-exercise", headers["owner"])
    assert result.status_code == 404
    assert db.scalars(select(MediaAsset)).all() == []
    assert list(root.iterdir()) == []
