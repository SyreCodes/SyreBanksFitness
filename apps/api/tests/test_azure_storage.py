from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from azure.core import MatchConditions
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.security import access_token
from app.modules.auth.models import User
from app.modules.cms.models import MediaAsset
from app.modules.cms.services import CMSService
from app.providers import azure_storage as azure_module
from app.providers.azure_storage import CHUNK_BYTES, AzureBlobStorage

CONTENT = b"0123456789"
MODIFIED = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
CLIENT_ID = "68624ec1-df89-4a74-a723-f557a426b9e4"


@pytest.fixture
def blob_provider(monkeypatch):
    blob = Mock()
    blob.get_blob_properties.return_value = SimpleNamespace(
        size=len(CONTENT), etag='"revision-1"', last_modified=MODIFIED,
    )

    def download(*, offset, length, **_kwargs):
        # The application must iterate chunks; the fake has no readall method.
        return SimpleNamespace(chunks=lambda: iter((CONTENT[offset:offset + length],)))

    blob.download_blob.side_effect = download
    client = Mock()
    client.get_blob_client.return_value = blob
    client_factory = Mock(return_value=client)
    credential_factory = Mock(return_value=object())
    monkeypatch.setattr(azure_module, "BlobServiceClient", client_factory)
    monkeypatch.setattr(azure_module, "ManagedIdentityCredential", credential_factory)
    provider = AzureBlobStorage("https://fitness.blob.core.windows.net", "fitness-media", CLIENT_ID)
    return provider, blob, client_factory, credential_factory


@pytest.fixture
def azure_media(client, db, monkeypatch, blob_provider):
    provider, blob, _, _ = blob_provider
    monkeypatch.setattr("app.modules.cms.routes.storage_provider", lambda: provider)
    monkeypatch.setattr("app.modules.cms.services.storage_provider", lambda: provider)
    owner = User(name="Owner", email="blob-owner@example.com", role="CLIENT", password_hash="fixture")
    other = User(name="Other", email="blob-other@example.com", role="CLIENT", password_hash="fixture")
    db.add_all([owner, other])
    db.flush()
    asset = MediaAsset(owner_id=owner.id, storage_key="opaque.mp4", content_type="video/mp4",
                       size=len(CONTENT), public=False, purpose="private")
    db.add(asset)
    db.commit()
    url = f"/api/v1/media/{asset.id}/file"
    headers = {"Authorization": f"Bearer {access_token(owner)}"}
    return client, db, asset, owner, other, url, headers, blob


def test_managed_identity_and_bounded_transfers(blob_provider):
    provider, blob, client_factory, credential_factory = blob_provider
    credential_factory.assert_called_once_with(client_id=CLIENT_ID)
    options = client_factory.call_args.kwargs
    assert options["account_url"] == "https://fitness.blob.core.windows.net"
    assert options["credential"] is credential_factory.return_value
    assert options["max_single_get_size"] == CHUNK_BYTES
    assert options["max_chunk_get_size"] == CHUNK_BYTES
    assert options["max_single_put_size"] == 4 * CHUNK_BYTES
    assert options["max_block_size"] == 4 * CHUNK_BYTES
    source = BytesIO(CONTENT)
    source.seek(5)
    provider.save_file("opaque.mp4", source, "video/mp4")
    assert source.tell() == 0
    assert blob.upload_blob.call_args.args[0] is source
    assert blob.upload_blob.call_args.kwargs["content_settings"].content_type == "video/mp4"
    assert blob.upload_blob.call_args.kwargs["max_concurrency"] == 1
    assert provider.signed_url("opaque.mp4") is None


@pytest.mark.parametrize(("range_header", "status", "body", "content_range", "offset", "length"), [
    (None, 200, CONTENT, None, 0, 10),
    ("bytes=2-5", 206, b"2345", "bytes 2-5/10", 2, 4),
    ("bytes=7-", 206, b"789", "bytes 7-9/10", 7, 3),
    ("bytes=-3", 206, b"789", "bytes 7-9/10", 7, 3),
    ("bytes=8-100", 206, b"89", "bytes 8-9/10", 8, 2),
    ("bytes=-100", 206, CONTENT, "bytes 0-9/10", 0, 10),
    ("items=2-5", 200, CONTENT, None, 0, 10),
    ("bytes=0-1,4-5", 200, CONTENT, None, 0, 10),
])
def test_video_response_ranges(azure_media, range_header, status, body, content_range, offset, length):
    client, _, _, _, _, url, headers, blob = azure_media
    response = client.get(url, headers={**headers, **({"Range": range_header} if range_header else {})})
    assert response.status_code == status
    assert response.content == body
    assert response.headers["Content-Length"] == str(len(body))
    assert response.headers.get("Content-Range") == content_range
    assert response.headers["Accept-Ranges"] == "bytes"
    assert response.headers["Content-Type"] == "video/mp4"
    assert response.headers["Cache-Control"] == "private, no-store"
    assert "Location" not in response.headers
    blob.download_blob.assert_called_once_with(
        offset=offset, length=length, max_concurrency=1,
        etag='"revision-1"', match_condition=MatchConditions.IfNotModified,
    )


@pytest.mark.parametrize("range_header", ["bytes=10-", "bytes=5-4", "bytes=-0", "bytes=abc-5", "bytes=-"])
def test_unsatisfiable_or_invalid_range_does_not_download(azure_media, range_header):
    client, _, _, _, _, url, headers, blob = azure_media
    response = client.get(url, headers={**headers, "Range": range_header})
    assert response.status_code == 416
    assert response.headers["Content-Range"] == "bytes */10"
    assert response.content == b""
    blob.download_blob.assert_not_called()


def test_head_returns_full_metadata_without_downloading(azure_media):
    client, _, _, _, _, url, headers, blob = azure_media
    response = client.head(url, headers={**headers, "Range": "bytes=2-5"})
    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["Content-Length"] == "10"
    assert response.headers["ETag"] == '"revision-1"'
    assert response.headers["Last-Modified"] == "Thu, 01 Oct 2026 12:00:00 GMT"
    assert "Content-Range" not in response.headers
    blob.download_blob.assert_not_called()


@pytest.mark.parametrize(("validator", "status", "body"), [
    ('"revision-1"', 206, b"23"),
    ("Thu, 01 Oct 2026 12:00:00 GMT", 206, b"23"),
    ('"old-revision"', 200, CONTENT),
    ('W/"revision-1"', 200, CONTENT),
])
def test_if_range_only_honors_current_strong_validator(azure_media, validator, status, body):
    client, _, _, _, _, url, headers, _ = azure_media
    response = client.get(url, headers={**headers, "Range": "bytes=2-3", "If-Range": validator})
    assert response.status_code == status
    assert response.content == body


def test_private_media_authorization_precedes_blob_access_and_tokens_revoke(azure_media):
    client, db, asset, owner, other, url, _, blob = azure_media
    assert client.get(url).status_code == 401
    assert client.head(url).status_code == 401
    assert client.get(url, headers={"Authorization": f"Bearer {access_token(other)}"}).status_code == 403
    blob.get_blob_properties.assert_not_called()

    signed = CMSService(db).media_output(asset, owner)["url"]
    assert signed.startswith(url + "?token=")
    assert client.get(signed).content == CONTENT
    owner.token_version += 1
    db.commit()
    blob.reset_mock()
    assert client.get(signed).status_code == 403
    blob.get_blob_properties.assert_not_called()


def test_publication_and_archive_take_effect_on_every_request(azure_media):
    client, db, asset, _, _, url, _, blob = azure_media
    asset.public = True
    db.commit()
    assert client.get(url).content == CONTENT
    asset.purpose = "archived"
    db.commit()
    blob.reset_mock()
    assert client.get(url).status_code == 404
    assert client.head(url).status_code == 404
    blob.get_blob_properties.assert_not_called()


@pytest.mark.parametrize(("error", "status", "code"), [
    (ResourceNotFoundError("internal storage location"), 404, "MEDIA_NOT_FOUND"),
    (HttpResponseError("internal storage location"), 503, "STORAGE_UNAVAILABLE"),
])
def test_storage_failures_are_sanitized(azure_media, error, status, code):
    client, _, _, _, _, url, headers, blob = azure_media
    blob.get_blob_properties.side_effect = error
    response = client.get(url, headers=headers)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "internal storage location" not in response.text


def test_zero_length_blob_does_not_start_a_download(azure_media):
    client, _, _, _, _, url, headers, blob = azure_media
    blob.get_blob_properties.return_value.size = 0
    response = client.get(url, headers=headers)
    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["Content-Length"] == "0"
    assert client.get(url, headers={**headers, "Range": "bytes=0-"}).status_code == 416
    blob.download_blob.assert_not_called()


def test_delete_missing_blob_is_idempotent_but_other_failures_are_reported(blob_provider):
    provider, blob, _, _ = blob_provider
    blob.delete_blob.side_effect = ResourceNotFoundError()
    provider.delete("missing.mp4")
    blob.delete_blob.assert_called_once_with(delete_snapshots="include")
    blob.delete_blob.side_effect = HttpResponseError()
    with pytest.raises(AppError, match="File storage is temporarily unavailable") as error:
        provider.delete("missing.mp4")
    assert error.value.status == 503


def test_azure_settings_accept_managed_identity_without_shared_keys():
    settings = Settings(
        _env_file=None, environment="production", database_url="postgresql://user:password@postgres/fitness",
        redis_url="rediss://cache.example.com:10000/0", jwt_secret="a" * 48,
        allowed_origins="https://fitness.example.com", public_web_url="https://fitness.example.com",
        storage_provider="azure", azure_storage_account_url="https://fitness.blob.core.windows.net",
        azure_storage_container="fitness-media", azure_managed_identity_client_id=CLIENT_ID,
    )
    assert settings.storage_provider == "azure"
    assert settings.s3_access_key == settings.s3_secret_key == ""


@pytest.mark.parametrize("invalid", [
    {"azure_storage_account_url": "http://fitness.blob.core.windows.net"},
    {"azure_storage_account_url": "https://fitness.blob.core.windows.net.evil.example"},
    {"azure_storage_account_url": "https://key@fitness.blob.core.windows.net"},
    {"azure_storage_account_url": "https://fitness.blob.core.windows.net?sig=secret"},
    {"azure_storage_account_url": "https://fitness.blob.core.windows.net/container"},
    {"azure_storage_container": "Invalid--Container"},
    {"azure_storage_container": ""},
    {"azure_managed_identity_client_id": "not-a-client-id"},
])
def test_azure_settings_reject_unsafe_or_invalid_configuration(invalid):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{
            "storage_provider": "azure", "azure_storage_account_url": "https://fitness.blob.core.windows.net",
            "azure_storage_container": "fitness-media", **invalid,
        })


@pytest.mark.parametrize("method", ["save", "save_file"])
def test_upload_failure_is_sanitized(blob_provider, method):
    provider, blob, _, _ = blob_provider
    blob.upload_blob.side_effect = HttpResponseError("private storage endpoint")
    payload = BytesIO(CONTENT) if method == "save_file" else CONTENT
    with pytest.raises(AppError, match="File storage is temporarily unavailable") as error:
        getattr(provider, method)("opaque.mp4", payload, "video/mp4")
    assert error.value.status == 503
    assert "private storage endpoint" not in str(error.value)


def test_s3_download_keeps_authorization_and_redirect_behavior(azure_media, monkeypatch):
    client, _, _, _, _, url, headers, _ = azure_media
    provider = Mock()
    provider.signed_url.return_value = "https://storage.example.com/private-object?signature=fixture"
    monkeypatch.setattr("app.modules.cms.routes.storage_provider", lambda: provider)
    assert client.get(url).status_code == 401
    provider.signed_url.assert_not_called()
    response = client.get(url, headers=headers, follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["Location"] == provider.signed_url.return_value
    provider.signed_url.assert_called_once_with("opaque.mp4")
