from __future__ import annotations

import logging

from app.core.config import settings
from app.core.security import hash_password
from app.db.mongo import DB
from app.models import Role, User
from app.services.settings_store import DEFAULTS, set_setting

log = logging.getLogger("dada.seed")


def seed(db: DB) -> None:
    """Idempotent first-boot data: the super-admin and the default app settings."""
    email = settings.ADMIN_EMAIL.lower()
    if not db.users.exists({"email": email}):
        db.users.insert(
            User(
                email=email,
                full_name="Dada Admin",
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                role=Role.superadmin,
                is_email_verified=True,
                is_premium=True,
            )
        )
        log.info("Seeded super-admin %s", email)

    for key, value in DEFAULTS.items():
        if not db.settings.get(key):
            set_setting(db, key, value)
