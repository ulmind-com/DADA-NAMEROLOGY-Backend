from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class Role(enum.StrEnum):
    user = "user"
    admin = "admin"
    superadmin = "superadmin"


class ReportType(enum.StrEnum):
    name = "name"
    business = "business"
    newborn = "newborn"
    mobile = "mobile"
    vehicle = "vehicle"


class OtpPurpose(enum.StrEnum):
    signup = "signup"
    login = "login"
    reset = "reset"
    email_change = "email_change"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), default="")
    phone: Mapped[str | None] = mapped_column(String(20), default=None)
    hashed_password: Mapped[str | None] = mapped_column(String(255), default=None)

    google_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, default=None)
    avatar_url: Mapped[str | None] = mapped_column(String(512), default=None)

    dob: Mapped[datetime | None] = mapped_column(Date, default=None)
    birth_time: Mapped[str | None] = mapped_column(String(16), default=None)
    birth_place: Mapped[str | None] = mapped_column(String(160), default=None)
    gender: Mapped[str | None] = mapped_column(String(16), default=None)

    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.user)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    premium_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    free_reports_used: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    reports: Mapped[list[Report]] = relationship(back_populates="user", cascade="all, delete-orphan")


class OtpCode(Base):
    __tablename__ = "otp_codes"
    __table_args__ = (Index("ix_otp_email_purpose", "email", "purpose"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[OtpPurpose] = mapped_column(Enum(OtpPurpose), default=OtpPurpose.signup)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    device: Mapped[str | None] = mapped_column(String(160), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True, default=None
    )
    type: Mapped[ReportType] = mapped_column(Enum(ReportType), index=True)
    tier: Mapped[str] = mapped_column(String(16), default="free")   # free | premium
    title: Mapped[str] = mapped_column(String(200), default="")
    subtitle: Mapped[str] = mapped_column(String(200), default="")
    score: Mapped[float | None] = mapped_column(Float, default=None)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)   # what the user submitted
    result: Mapped[dict] = mapped_column(JSON, default=dict)    # what the engine returned
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    user: Mapped[User] = relationship(back_populates="reports")


class Rule(Base):
    """Admin-editable override of a bundled numerology rule."""

    __tablename__ = "rules"
    __table_args__ = (Index("ix_rule_kind_key", "kind", "key", unique=True),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(40), index=True)  # compound_meanings | root_profiles | pair_meanings
    key: Mapped[str] = mapped_column(String(40), index=True)   # "28" | "5" | "9:5"
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_by: Mapped[str | None] = mapped_column(String(32), default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    actor_id: Mapped[str | None] = mapped_column(String(32), index=True, default=None)
    actor_email: Mapped[str] = mapped_column(String(255), default="")
    action: Mapped[str] = mapped_column(String(80), index=True)
    target: Mapped[str] = mapped_column(String(160), default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
