import secrets
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any

import jwt
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.permissions import ADMIN_ROLES, client_scope, require_admin
from app.core.repository import paginate, persist, require_record, serialize
from app.modules.auth.models import User
from app.modules.clients.models import Consent
from app.modules.cms.models import BlogPost, MediaAsset, Setting
from app.modules.cms.schemas import BlogInput, SettingsPatch
from app.providers.storage import storage_provider

DEFAULT_CONTENT: dict[str, Any] = {
    "brand": "Syre Banks Fitness", "hero_heading": "BUILD THE BODY.\nBUILD THE DISCIPLINE.\nBUILD THE LIFE.",
    "hero_description": "Personalized online coaching built around your goals, your lifestyle and the work you put in.",
    "hero_image_url": get_settings().public_web_url.rstrip("/") + "/images/training-illustration.jpg",
    "hero_image_caption": "Illustrative training photography · Luke Witter / Unsplash",
    "about_heading": "Discipline that carries into life.",
    "about_bio": "Syre Banks Fitness brings structured training, consistent accountability and personal coaching together. Coach biography and qualifications will be added after verification.",
    "about_image_url": "", "coaching_philosophy": "Start where you are. Train with intention. Build habits that last.",
    "contact_email": "syrefitness6@gmail.com", "contact_phone": "0785430927",
    "instagram_url": "https://www.instagram.com/williamsyre2.0/", "tiktok_url": "https://www.tiktok.com/@mugabo.willy",
    "transformations": [], "testimonials": [], "services": [], "faq": [],
    "legal_version": "2026-01",
    "legal": {key: "REVIEW DRAFT — This policy requires review for the applicable jurisdiction before launch. Coaching provides general fitness guidance and is not medical diagnosis or treatment. Contact syrefitness6@gmail.com with questions." for key in ["privacy", "terms", "disclaimer", "cookies", "refund", "coaching", "liability", "photo"]},
    "availability": {"timezone": "Africa/Kigali", "weekdays": [0, 1, 2, 3, 4], "hours": [9, 11, 14, 16], "duration_minutes": 60},
    "feature_flags": {"nutrition_enabled": True, "community_enabled": False, "live_training_enabled": True, "ai_features_enabled": False, "wearables_enabled": False},
}


async def read_validated_upload(file: UploadFile) -> tuple[bytes, str, str]:
    maximum = get_settings().max_upload_bytes
    content = await file.read(maximum + 1)
    if not content or len(content) > maximum:
        raise AppError(413, "FILE_TOO_LARGE", "Upload a nonempty file smaller than 10 MB")
    types = {"image/jpeg": ("jpg", content.startswith(b"\xff\xd8\xff")), "image/png": ("png", content.startswith(b"\x89PNG\r\n\x1a\n")), "image/webp": ("webp", content[:4] == b"RIFF" and content[8:12] == b"WEBP"), "application/pdf": ("pdf", content.startswith(b"%PDF-")), "video/mp4": ("mp4", len(content) > 12 and content[4:8] == b"ftyp")}
    kind = file.content_type or ""
    if kind not in types or not types[kind][1]:
        raise AppError(422, "INVALID_FILE_TYPE", "Upload a valid JPEG, PNG, WebP, PDF or MP4 file")
    if kind.startswith("image/"):
        from PIL import Image, UnidentifiedImageError
        try:
            with Image.open(BytesIO(content)) as picture:
                expected = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}[kind]
                if picture.format != expected or picture.width * picture.height > 25_000_000:
                    raise ValueError("Invalid image dimensions or format")
                picture.verify()
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
            raise AppError(422, "INVALID_IMAGE", "Upload a valid image of no more than 25 megapixels") from exc
    return content, kind, types[kind][0]


class CMSService:
    def __init__(self, db: Session):
        self.db = db

    def settings(self) -> dict:
        record = self.db.scalar(select(Setting).where(Setting.key == "business"))
        return {**DEFAULT_CONTENT, **(record.value if record else {})}

    def publication_consent(self, client_id: str | None) -> bool:
        if not client_id:
            return False
        consent = self.db.scalar(select(Consent).where(Consent.client_id == client_id, Consent.kind == "photo").order_by(Consent.created_at.desc()).limit(1))
        return bool(consent and consent.accepted and consent.version == self.settings()["legal_version"])

    def public_content(self) -> dict:
        content = self.settings()
        # API publication gates apply again when consent is withdrawn.
        content["transformations"] = [item for item in content.get("transformations", []) if item.get("consent_status") in {"GRANTED", "PUBLISHED"} and self.publication_consent(item.get("client_id"))]
        content["testimonials"] = [item for item in content.get("testimonials", []) if item.get("publication_consent") is True and self.publication_consent(item.get("client_id"))]
        return content

    def patch_settings(self, data: SettingsPatch, user: User) -> dict:
        require_admin(user)
        record = self.db.scalar(select(Setting).where(Setting.key == "business"))
        existing = self.settings()
        incoming = data.model_dump(exclude_unset=True, mode="json")
        # Rewriting legal text requires a new version; accepted consents snapshot the old text.
        if "legal" in incoming and incoming["legal"] != existing["legal"] and incoming.get("legal_version", existing["legal_version"]) == existing["legal_version"]:
            raise AppError(409, "LEGAL_VERSION_REQUIRED", "Increment the legal version when changing policy text")
        for key in ["transformations", "testimonials"]:
            for item in incoming.get(key) or []:
                requested = item.get("consent_status") in {"GRANTED", "PUBLISHED"} or item.get("publication_consent") is True
                if requested and not self.publication_consent(item.get("client_id")):
                    raise AppError(422, "PUBLICATION_CONSENT_REQUIRED", "Client publication consent is required")
                for field, value in item.items():
                    if (field.endswith("url") or field.endswith("image")) and value and (not isinstance(value, str) or not value.startswith(("https://", "http://"))):
                        raise AppError(422, "INVALID_MEDIA_URL", "Use an HTTP or HTTPS media URL")
        if not record:
            record = Setting(key="business", value={})
        record.value = {**existing, **incoming}
        persist(self.db, record, user.id, "settings.updated")
        return self.settings()

    def blog(self, user: User | None, limit: int, offset: int) -> dict:
        stmt = select(BlogPost)
        if not user or user.role not in ADMIN_ROLES:
            stmt = stmt.where(BlogPost.published.is_(True))
        return paginate(self.db, stmt.order_by(BlogPost.created_at.desc()), limit, offset)

    def blog_detail(self, slug: str, user: User | None) -> dict:
        post = self.db.scalar(select(BlogPost).where(BlogPost.slug == slug))
        if not post or (not post.published and (not user or user.role not in ADMIN_ROLES)):
            raise AppError(404, "BLOG_NOT_FOUND", "Article not found")
        return serialize(post)

    def save_blog(self, data: BlogInput, user: User, post_id: str | None = None) -> dict:
        require_admin(user)
        post = require_record(self.db, BlogPost, post_id) if post_id else BlogPost(author_id=user.id)
        for key, value in data.model_dump(mode="json").items():
            setattr(post, key, value)
        try:
            return persist(self.db, post, user.id, "blog.updated" if post_id else "blog.created")
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(409, "SLUG_EXISTS", "An article with this URL already exists") from exc

    def media_output(self, asset: MediaAsset, user: User) -> dict:
        values = {key: value for key, value in serialize(asset).items()
                  if key not in {"storage_key", "upload_id", "upload_sha256"}}
        if asset.public:
            values["url"] = f"/api/v1/media/{asset.id}/file"
        else:
            signed = storage_provider().signed_url(asset.storage_key)
            token = jwt.encode({"sub": user.id, "ver": user.token_version, "media_id": asset.id, "type": "media", "exp": datetime.now(UTC) + timedelta(minutes=5), "aud": "media", "iss": "syre-banks-fitness"}, get_settings().jwt_secret, algorithm="HS256")
            values["url"] = signed or f"/api/v1/media/{asset.id}/file?token={token}"
        return values

    def media(self, user: User, limit: int, offset: int) -> dict:
        stmt = select(MediaAsset).where(MediaAsset.purpose != "archived")
        if user.role not in ADMIN_ROLES:
            if user.role == "COACH":
                stmt = stmt.where((MediaAsset.owner_id == user.id) | MediaAsset.owner_id.in_(select(User.id).where(User.assigned_coach_id == user.id)))
            else:
                stmt = stmt.where(MediaAsset.owner_id == user.id)
        page = paginate(self.db, stmt.order_by(MediaAsset.created_at.desc()), limit, offset)
        page["items"] = [self.media_output(require_record(self.db, MediaAsset, item["id"]), user) for item in page["items"]]
        return page

    async def upload(self, file: UploadFile, caption: str, purpose: str, public: bool, user: User) -> dict:
        if len(caption) > 300 or purpose not in {"marketing", "exercise", "progress", "profile", "document", "private"}:
            raise AppError(422, "INVALID_MEDIA", "Invalid media metadata")
        if public:
            require_admin(user)
            if purpose not in {"marketing", "exercise"}:
                raise AppError(422, "PRIVATE_MEDIA_REQUIRED", "Client progress media must remain private")
        content, kind, extension = await read_validated_upload(file)
        if public and kind == "application/pdf":
            raise AppError(422, "PRIVATE_MEDIA_REQUIRED", "Documents are private")
        key = secrets.token_hex(24) + "." + extension
        storage_provider().save(key, content, kind)
        asset = MediaAsset(owner_id=user.id, storage_key=key, content_type=kind, size=len(content), caption=caption, purpose=purpose, public=public)
        persist(self.db, asset, user.id, "media.uploaded")
        return self.media_output(asset, user)

    def authorize_asset(self, asset: MediaAsset, user: User) -> None:
        if asset.owner_id != user.id and user.role not in ADMIN_ROLES:
            client_scope(self.db, user, asset.owner_id)

    def edit_media(self, media_id: str, caption: str | None, archive: bool, user: User) -> dict:
        asset = require_record(self.db, MediaAsset, media_id)
        self.authorize_asset(asset, user)
        if archive:
            asset.purpose, asset.public = "archived", False
        if caption is not None:
            asset.caption = caption
        persist(self.db, asset, user.id, "media.archived" if archive else "media.updated")
        return self.media_output(asset, user)
