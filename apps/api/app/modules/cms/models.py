from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Record


class Setting(Record, Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(100), unique=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)


class BlogPost(Record, Base):
    __tablename__ = "blog_posts"
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    excerpt: Mapped[str] = mapped_column(String(500), default="")
    body: Mapped[str] = mapped_column(Text)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    cover_url: Mapped[str | None] = mapped_column(String(1000))
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    demo: Mapped[bool] = mapped_column(Boolean, default=False)


class MediaAsset(Record, Base):
    __tablename__ = "media_assets"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(300), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    caption: Mapped[str] = mapped_column(String(300), default="")
    purpose: Mapped[str] = mapped_column(String(40), default="private")
    public: Mapped[bool] = mapped_column(Boolean, default=False)
    upload_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    upload_sha256: Mapped[str | None] = mapped_column(String(64))
