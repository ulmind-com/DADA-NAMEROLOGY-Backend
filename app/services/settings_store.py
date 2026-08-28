from __future__ import annotations

from typing import Any

from app.db.mongo import DB
from app.models import AppSetting, utcnow

DEFAULTS: dict[str, dict[str, Any]] = {
    "free_full_reports": {"value": 1, "label": "Free detailed reports per user"},
    "premium_price_inr": {"value": 499, "label": "Premium price (INR)"},
    "vehicle_enabled": {"value": True, "label": "Vehicle numerology live"},
    "maintenance": {"value": False, "message": "", "label": "Maintenance mode"},
    "support_whatsapp": {"value": "", "label": "Support WhatsApp number"},
    "announcement": {"value": "", "label": "Home screen announcement"},
}


def get_setting(db: DB, key: str, default: dict | None = None) -> dict:
    row = db.settings.get(key)
    if row:
        return row.value or {}
    return default if default is not None else DEFAULTS.get(key, {})


def set_setting(db: DB, key: str, value: dict) -> dict:
    db.settings.upsert({"_id": key}, {"value": value, "updated_at": utcnow()})
    return value


def all_settings(db: DB) -> dict[str, dict]:
    out = dict(DEFAULTS)
    for row in db.settings.find():
        out[row.id] = row.value
    return out


__all__ = ["DEFAULTS", "AppSetting", "all_settings", "get_setting", "set_setting"]
