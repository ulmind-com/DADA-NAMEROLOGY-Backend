from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AppSetting

DEFAULTS: dict[str, dict[str, Any]] = {
    "free_full_reports": {"value": 1, "label": "Free detailed reports per user"},
    "premium_price_inr": {"value": 499, "label": "Premium price (INR)"},
    "vehicle_enabled": {"value": True, "label": "Vehicle numerology live"},
    "maintenance": {"value": False, "message": "", "label": "Maintenance mode"},
    "support_whatsapp": {"value": "", "label": "Support WhatsApp number"},
    "announcement": {"value": "", "label": "Home screen announcement"},
}


def get_setting(db: Session, key: str, default: dict | None = None) -> dict:
    row = db.get(AppSetting, key)
    if row:
        return row.value or {}
    return default if default is not None else DEFAULTS.get(key, {})


def set_setting(db: Session, key: str, value: dict) -> dict:
    row = db.get(AppSetting, key)
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    db.commit()
    return value


def all_settings(db: Session) -> dict[str, dict]:
    out = dict(DEFAULTS)
    for row in db.query(AppSetting).all():
        out[row.key] = row.value
    return out
