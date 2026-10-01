import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LearningApp(Base):
    __tablename__ = "learning_apps"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    active_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_versions.id", name="fk_apps_active_version", use_alter=True)
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    account: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(16), default="user")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    avatar_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("uploads.id", use_alter=True, name="fk_user_avatar")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoginSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginBucket(Base):
    __tablename__ = "login_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AppDraft(Base):
    __tablename__ = "app_drafts"
    app_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_apps.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(2000), default="")
    app_type: Mapped[str] = mapped_column(String(16), default="assessment")
    strategy: Mapped[str] = mapped_column(String(16), default="rules")
    content: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    cover_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("uploads.id"))


class AppVersion(Base):
    __tablename__ = "app_versions"
    __table_args__ = (UniqueConstraint("app_id", "sequence", name="uq_app_version_sequence"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    app_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_apps.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(2000))
    app_type: Mapped[str] = mapped_column(String(16))
    strategy: Mapped[str] = mapped_column(String(16))
    content: Mapped[dict[str, object]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    strategy_version: Mapped[str] = mapped_column(String(64), default="rules-v1")
    cover_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("uploads.id"))


class PublicationReview(Base):
    __tablename__ = "publication_reviews"
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_versions.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(2000), default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("owner_id", "idempotency_key", name="uq_answer_owner_key"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    app_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_apps.id"), index=True)
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_versions.id"), index=True)
    choices: Mapped[list[str]] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16))
    result_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Upload(Base):
    __tablename__ = "uploads"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(16))
    media_type: Mapped[str] = mapped_column(String(32))
    size: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UploadReference(Base):
    __tablename__ = "upload_references"
    upload_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("uploads.id"), primary_key=True)
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_versions.id"), primary_key=True)
