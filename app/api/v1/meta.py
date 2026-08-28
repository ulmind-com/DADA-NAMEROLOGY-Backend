from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.db.mongo import DB, get_db
from app.services.settings_store import all_settings

router = APIRouter(tags=["meta"])


@router.get("/health")
def health(db: DB = Depends(get_db)):
    try:
        db.raw.client.admin.command("ping")
        database = "up"
    except Exception:
        database = "down"
    return {"status": "ok", "env": settings.ENV, "app": settings.PROJECT_NAME, "database": database}


@router.get("/config", summary="Public runtime config the mobile app reads on launch")
def public_config(db: DB = Depends(get_db)):
    s = all_settings(db)
    return {
        "app_name": settings.PROJECT_NAME,
        "vehicle_enabled": bool(s.get("vehicle_enabled", {}).get("value", True)),
        "free_full_reports": s.get("free_full_reports", {}).get("value", 1),
        "premium_price_inr": s.get("premium_price_inr", {}).get("value", 499),
        "announcement": s.get("announcement", {}).get("value", ""),
        "support_whatsapp": s.get("support_whatsapp", {}).get("value", ""),
        "uploads_enabled": settings.cloudinary_enabled,
        "maintenance": {
            "enabled": bool(s.get("maintenance", {}).get("value", False)),
            "message": s.get("maintenance", {}).get("message", ""),
        },
        "modules": [
            {"key": "name", "title": "Name Numerology", "enabled": True},
            {"key": "mobile", "title": "Mobile Numerology", "enabled": True},
            {"key": "vehicle", "title": "Vehicle Numerology",
             "enabled": bool(s.get("vehicle_enabled", {}).get("value", True))},
        ],
    }
