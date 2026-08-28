from __future__ import annotations

import logging

from fastapi import HTTPException, status

from app.core.config import settings

log = logging.getLogger("dada.google")


def verify_google_id_token(token: str) -> dict:
    """Validate a Google ID token and return the normalised profile."""
    try:
        from google.auth.transport import requests as g_requests
        from google.oauth2 import id_token as g_id_token
    except ImportError:  # pragma: no cover
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "google-auth is not installed") from None

    request = g_requests.Request()
    info = None
    last_error: Exception | None = None

    audiences = settings.GOOGLE_CLIENT_IDS or [None]
    for aud in audiences:
        try:
            info = g_id_token.verify_oauth2_token(token, request, aud)
            break
        except Exception as exc:
            last_error = exc

    if not info:
        log.warning("Google token rejected: %s", last_error)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Google sign-in could not be verified.")

    if info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token issuer.")
    if not info.get("email"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Google account has no email address.")

    return {
        "google_id": info["sub"],
        "email": info["email"].lower(),
        "email_verified": bool(info.get("email_verified")),
        "name": info.get("name") or "",
        "picture": info.get("picture"),
    }
