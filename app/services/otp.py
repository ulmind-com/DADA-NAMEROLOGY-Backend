from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_otp, hash_otp, verify_otp
from app.models import OtpCode, OtpPurpose
from app.services.email import send_otp_email


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def issue_otp(db: Session, email: str, purpose: OtpPurpose, name: str = "") -> dict:
    email = email.lower().strip()

    latest = db.scalars(
        select(OtpCode)
        .where(OtpCode.email == email, OtpCode.purpose == purpose, OtpCode.consumed_at.is_(None))
        .order_by(OtpCode.created_at.desc())
    ).first()

    if latest:
        age = (_now() - _aware(latest.created_at)).total_seconds()
        if age < settings.OTP_RESEND_SECONDS:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {int(settings.OTP_RESEND_SECONDS - age)}s before requesting a new code.",
            )
        latest.consumed_at = _now()

    code = generate_otp()
    row = OtpCode(
        email=email,
        code_hash=hash_otp(code),
        purpose=purpose,
        expires_at=_now() + timedelta(minutes=settings.OTP_TTL_MINUTES),
    )
    db.add(row)
    db.commit()

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


def check_otp(db: Session, email: str, code: str, purpose: OtpPurpose) -> None:
    email = email.lower().strip()
    row = db.scalars(
        select(OtpCode)
        .where(OtpCode.email == email, OtpCode.purpose == purpose, OtpCode.consumed_at.is_(None))
        .order_by(OtpCode.created_at.desc())
    ).first()

    if not row:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No active code. Please request a new one.")
    if _aware(row.expires_at) < _now():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This code has expired. Request a new one.")
    if row.attempts >= settings.OTP_MAX_ATTEMPTS:
        row.consumed_at = _now()
        db.commit()
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many wrong attempts. Request a new code.")

    if not verify_otp(code.strip(), row.code_hash):
        row.attempts += 1
        db.commit()
        left = settings.OTP_MAX_ATTEMPTS - row.attempts
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Incorrect code. {left} attempt(s) left.")

    row.consumed_at = _now()
    db.commit()
