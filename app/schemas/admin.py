from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class AdminStatsOut(BaseModel):
    users_total: int
    users_today: int
    users_week: int
    premium_users: int
    reports_total: int
    reports_today: int
    reports_by_type: dict[str, int]
    signups_series: list[dict[str, Any]]
    reports_series: list[dict[str, Any]]
    top_numbers: list[dict[str, Any]]
    recent_users: list[dict[str, Any]]
    recent_reports: list[dict[str, Any]]


class AdminUserOut(BaseModel):
    id: str
    email: str
    full_name: str
    phone: str | None
    role: str
    is_active: bool
    is_premium: bool
    is_email_verified: bool
    provider: str
    reports_count: int
    created_at: datetime
    last_login_at: datetime | None


class AdminUserUpdateIn(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    role: str | None = None
    is_active: bool | None = None
    is_premium: bool | None = None


class RuleUpsertIn(BaseModel):
    kind: str = Field(pattern="^(name_chart|vehicle_master|vehicle_patterns|pair_meanings)$")
    key: str
    data: dict[str, Any]


class SettingIn(BaseModel):
    key: str
    value: dict[str, Any]


class AdminCreateIn(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8)
    role: str = "admin"


class BroadcastIn(BaseModel):
    subject: str = Field(min_length=3, max_length=140)
    body: str = Field(min_length=3)
    audience: str = Field(default="all", pattern="^(all|premium|free)$")
