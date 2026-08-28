from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from app.core.config import settings
from app.core.security import generate_otp, hash_otp, verify_otp
from app.db.mongo import DB, DESC
from app.models import OtpCode, OtpPurpose
from app.services.email import send_otp_email


def _now() -> datetime:
    return datetime.now(UTC)


def _latest(db: DB, email: str, purpose: OtpPurpose) -> OtpCode | None:
    rows = db.otps.find(
        {"email": email, "purpose": purpose, "consumed_at": None},
        sort=[("created_at", DESC)],
        limit=1,
    )
    return rows[0] if rows else None


def issue_otp(db: DB, email: str, purpose: OtpPurpose, name: str = "") -> dict:
    email = email.lower().strip()

    latest = _latest(db, email, purpose)
    if latest:
        age = (_now() - latest.created_at).total_seconds()
        if age < settings.OTP_RESEND_SECONDS:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {int(settings.OTP_RESEND_SECONDS - age)}s before requesting a new code.",
            )
        db.otps.update(latest.id, {"consumed_at": _now()})

    code = generate_otp()
    db.otps.insert(
        OtpCode(
            email=email,
            code_hash=hash_otp(code),
            purpose=purpose,
            expires_at=_now() + timedelta(minutes=settings.OTP_TTL_MINUTES),
        )
    )

    delivered = send_otp_email(email, code, purpose.value, name)

    out = {
        "email": email,
        "expires_in": settings.OTP_TTL_MINUTES * 60,
        "resend_in": settings.OTP_RESEND_SECONDS,
        "delivered": delivered,
    }
    if settings.OTP_DEV_ECHO and not delivered:
        # dev convenience only - never enabled in production
        out["dev_otp"] = code
    return out


def check_otp(db: DB, email: str, code: str, purpose: OtpPurpose) -> None:
    email = email.lower().strip()
    row = _latest(db, email, purpose)

    if not row:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No active code. Please request a new one.")
    if row.expires_at < _now():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This code has expired. Request a new one.")
    if row.attempts >= settings.OTP_MAX_ATTEMPTS:
        db.otps.update(row.id, {"consumed_at": _now()})
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many wrong attempts. Request a new code."
        )

    if not verify_otp(code.strip(), row.code_hash):
        db.otps.increment(row.id, "attempts")
        left = settings.OTP_MAX_ATTEMPTS - (row.attempts + 1)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Incorrect code. {left} attempt(s) left.")

    db.otps.update(row.id, {"consumed_at": _now()})
