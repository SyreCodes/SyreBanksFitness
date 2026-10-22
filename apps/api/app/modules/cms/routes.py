import jwt
from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.permissions import DB, Identity, OptionalIdentity, require_admin
from app.core.repository import require_record
from app.modules.auth.models import User
from app.modules.cms.models import BlogPost, MediaAsset
from app.modules.cms.schemas import BlogInput, MediaPatch, SettingsPatch
from app.modules.cms.services import CMSService
from app.modules.coaching.models import Exercise
from app.providers.azure_storage import AzureBlobStorage
from app.providers.storage import LocalStorage, storage_provider

router = APIRouter(tags=["Content and media"])


@router.get("/public/content")
@router.get("/content/public")
def content(db: DB):
    return CMSService(db).public_content()


@router.get("/settings")
def settings(db: DB, user: Identity):
    require_admin(user)
    return CMSService(db).settings()


@router.patch("/settings")
def update_settings(data: SettingsPatch, db: DB, user: Identity):
    return CMSService(db).patch_settings(data, user)


@router.get("/blog")
def posts(db: DB, user: OptionalIdentity, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return CMSService(db).blog(user, limit, offset)


@router.get("/blog/{slug}")
def article(slug: str, db: DB, user: OptionalIdentity):
    return CMSService(db).blog_detail(slug, user)


@router.post("/blog", status_code=201)
def create_post(data: BlogInput, db: DB, user: Identity):
    return CMSService(db).save_blog(data, user)


@router.patch("/blog/{post_id}")
def update_post(post_id: str, data: BlogInput, db: DB, user: Identity):
    return CMSService(db).save_blog(data, user, post_id)


@router.delete("/blog/{post_id}")
def unpublish(post_id: str, db: DB, user: Identity):
    require_admin(user)
    post = require_record(db, BlogPost, post_id)
    post.published = False
    db.commit()
    return {"message": "Article unpublished"}


@router.get("/media")
def media(db: DB, user: Identity, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return CMSService(db).media(user, limit, offset)


@router.post("/media", status_code=201)
async def upload(db: DB, user: Identity, file: UploadFile = File(), caption: str = Form(""), purpose: str = Form("private"), public: bool = Form(False)):
    return await CMSService(db).upload(file, caption, purpose, public, user)


@router.patch("/media/{media_id}")
def edit_media(media_id: str, data: MediaPatch, db: DB, user: Identity):
    return CMSService(db).edit_media(media_id, data.caption, False, user)


@router.delete("/media/{media_id}")
def archive(media_id: str, db: DB, user: Identity):
    return CMSService(db).edit_media(media_id, None, True, user)


@router.api_route("/media/{media_id}/file", methods=["GET", "HEAD"])
def file_download(media_id: str, db: DB, user: OptionalIdentity, request: Request, token: str | None = None):
    asset = require_record(db, MediaAsset, media_id)
    if asset.purpose == "archived":
        raise AppError(404, "MEDIA_NOT_FOUND", "Media is no longer available")
    exercise = db.scalar(select(Exercise).where(Exercise.video_media_id == asset.id))
    if not asset.public or (exercise is not None and not exercise.published):
        if token:
            try:
                claims = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"], audience="media", issuer="syre-banks-fitness", options={"require": ["sub", "exp", "media_id", "type", "ver"]})
                candidate = db.get(User, claims["sub"])
                if claims["media_id"] != asset.id or claims["type"] != "media" or not candidate or not candidate.active or claims["ver"] != candidate.token_version:
                    raise ValueError("Invalid media token")
                user = candidate
            except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
                raise AppError(403, "INVALID_MEDIA_TOKEN", "This media link has expired") from exc
        if not user:
            raise AppError(401, "PRIVATE_MEDIA", "Please sign in to access private media")
        CMSService(db).authorize_asset(asset, user)
    provider = storage_provider()
    if isinstance(provider, AzureBlobStorage):
        return provider.response(asset.storage_key, asset.content_type, method=request.method,
                                 range_header=request.headers.get("range"), if_range=request.headers.get("if-range"))
    if isinstance(provider, LocalStorage):
        return FileResponse(provider.path(asset.storage_key), media_type=asset.content_type, headers={"Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"})
    url = provider.signed_url(asset.storage_key)
    if url is None:
        raise AppError(503, "STORAGE_UNAVAILABLE", "Storage is unavailable")
    return RedirectResponse(url)
