from __future__ import annotations

import logging

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.db.mongo import DB
from app.models import Role, User
from app.services.settings_store import DEFAULTS, set_setting

log = logging.getLogger("dada.seed")


def seed(db: DB) -> None:
    """Idempotent first-boot data: the super-admin and the default app settings."""
    email = settings.ADMIN_EMAIL.lower()
    existing = db.users.find_one({"email": email})

    if not existing:
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
    elif not verify_password(settings.ADMIN_PASSWORD, existing.hashed_password):
        # ADMIN_PASSWORD only applies when the account is first created; it must not
        # silently overwrite a password that was deliberately changed later.
        log.warning(
            "Super-admin %s already exists and its password differs from ADMIN_PASSWORD. "
            "The stored password still applies — change it from the admin panel, or "
            "delete the account to have it re-seeded.",
            email,
        )

    for key, value in DEFAULTS.items():
        if not db.settings.get(key):
            set_setting(db, key, value)
