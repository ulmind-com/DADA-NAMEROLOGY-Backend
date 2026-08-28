"""MongoDB documents.

Pydantic models with a Mongo `_id` alias, so route code keeps real attribute access
(`user.email`, `report.type`) instead of juggling raw dictionaries.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.db.mongo import encode


def new_id() -> str:
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


class Doc(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: str = Field(default_factory=new_id, alias="_id")

    def to_mongo(self) -> dict[str, Any]:
        return encode(self.model_dump(by_alias=True))


class User(Doc):
    email: str
    full_name: str = ""
    phone: str | None = None
    hashed_password: str | None = None

    google_id: str | None = None
    avatar_url: str | None = None
    avatar_public_id: str | None = None   # Cloudinary handle, so old images can be replaced

    dob: date | None = None
    birth_time: str | None = None
    birth_place: str | None = None
    gender: str | None = None

    role: Role = Role.user
    is_active: bool = True
    is_email_verified: bool = False
    is_premium: bool = False
    premium_until: datetime | None = None
    free_reports_used: int = 0

    created_at: datetime = Field(default_factory=utcnow)
    last_login_at: datetime | None = None

    @property
    def provider(self) -> str:
        if self.google_id and self.hashed_password:
            return "google+password"
        return "google" if self.google_id else "password"


class OtpCode(Doc):
    email: str
    code_hash: str
    purpose: OtpPurpose = OtpPurpose.signup
    attempts: int = 0
    expires_at: datetime
    consumed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class RefreshToken(Doc):
    user_id: str
    token_hash: str
    expires_at: datetime
    revoked: bool = False
    device: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Report(Doc):
    user_id: str | None = None
    type: ReportType
    tier: str = "free"                     # free | premium
    title: str = ""
    subtitle: str = ""
    score: float | None = None
    payload: dict[str, Any] = Field(default_factory=dict)   # what the user submitted
    result: dict[str, Any] = Field(default_factory=dict)    # what the engine returned
    pdf_url: str | None = None             # Cloudinary link, set on first download
    pdf_public_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Rule(Doc):
    """Admin-editable override of a bundled numerology rule."""

    kind: str                              # compound_meanings | root_profiles | pair_meanings
    key: str                               # "28" | "5" | "9:5"
    data: dict[str, Any] = Field(default_factory=dict)
    updated_by: str | None = None
    updated_at: datetime = Field(default_factory=utcnow)


class AppSetting(Doc):
    """`_id` is the setting key, so lookups are a primary-key hit."""

    id: str = Field(alias="_id")
    value: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=utcnow)


class AuditLog(Doc):
    actor_id: str | None = None
    actor_email: str = ""
    action: str = ""
    target: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)
    note: str = ""
    created_at: datetime = Field(default_factory=utcnow)
