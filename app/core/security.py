from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ------------------------------------------------------------------ passwords
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


# ---------------------------------------------------------------------- otp
def generate_otp(length: int | None = None) -> str:
    n = length or settings.OTP_LENGTH
    return "".join(secrets.choice("0123456789") for _ in range(n))


def hash_otp(code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), code.encode(), hashlib.sha256).hexdigest()


def verify_otp(code: str, code_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(code), code_hash)


# -------------------------------------------------------------------- tokens
def _create_token(subject: str, expires: timedelta, token_type: str, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires).timestamp()),
        "jti": secrets.token_hex(8),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: str, role: str = "user") -> str:
    return _create_token(
        user_id, timedelta(minutes=settings.ACCESS_TOKEN_MINUTES), "access", {"role": role}
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(user_id, timedelta(days=settings.REFRESH_TOKEN_DAYS), "refresh")


def create_signup_token(email: str) -> str:
    """Short-lived proof that this email passed OTP verification."""
    return _create_token(
        email, timedelta(minutes=settings.SIGNUP_TOKEN_MINUTES), "signup", {"email": email}
    )


def create_reset_token(email: str) -> str:
    return _create_token(
        email, timedelta(minutes=settings.SIGNUP_TOKEN_MINUTES), "reset", {"email": email}
    )


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    if expected_type and payload.get("type") != expected_type:
        return None
    return payload


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
