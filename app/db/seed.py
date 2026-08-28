from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models import Role, User
from app.services.settings_store import DEFAULTS, get_setting, set_setting

log = logging.getLogger("dada.seed")


def seed(db: Session) -> None:
    admin = db.scalars(select(User).where(User.email == settings.ADMIN_EMAIL.lower())).first()
    if not admin:
        db.add(
            User(
                email=settings.ADMIN_EMAIL.lower(),
                full_name="Dada Admin",
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                role=Role.superadmin,
                is_email_verified=True,
                is_premium=True,
            )
        )
        db.commit()
        log.info("Seeded super-admin %s", settings.ADMIN_EMAIL)

    for key, value in DEFAULTS.items():
        if not get_setting(db, key, {}):
            set_setting(db, key, value)
