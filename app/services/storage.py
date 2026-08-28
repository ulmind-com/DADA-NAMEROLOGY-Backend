"""Cloudinary uploads — profile photos and stored PDF reports.

Signed uploads are made directly against the REST API with httpx, so no extra SDK is
pulled in. When Cloudinary is not configured every call is a no-op that returns None,
and the app carries on: avatars simply stay unset and PDFs are streamed from the API.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Literal

import httpx

from app.core.config import settings

log = logging.getLogger("dada.storage")

ResourceType = Literal["image", "raw", "video"]

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}

_API = "https://api.cloudinary.com/v1_1"


def _sign(params: dict[str, str]) -> str:
    """Cloudinary signature: sha1 of the sorted params plus the API secret."""
    signable = {
        k: v
        for k, v in params.items()
        if k not in ("file", "api_key", "resource_type", "cloud_name") and v not in (None, "")
    }
    payload = "&".join(f"{k}={signable[k]}" for k in sorted(signable))
    return hashlib.sha1(f"{payload}{settings.CLOUDINARY_CLOUD_SECRET}".encode()).hexdigest()


def upload(
    content: bytes,
    *,
    filename: str,
    folder: str,
    resource_type: ResourceType = "image",
    public_id: str | None = None,
    content_type: str | None = None,
) -> dict | None:
    """Returns `{"url", "public_id", "bytes", "format"}`, or None when unavailable."""
    if not settings.cloudinary_enabled:
        log.info("Cloudinary not configured — skipping upload of %s", filename)
        return None

    timestamp = str(int(time.time()))
    params: dict[str, str] = {
        "timestamp": timestamp,
        "folder": f"{settings.CLOUDINARY_FOLDER}/{folder}",
        "overwrite": "true",
    }
    if public_id:
        params["public_id"] = public_id

    data = {**params, "api_key": settings.CLOUDINARY_CLOUD_API_KEY, "signature": _sign(params)}

    try:
        res = httpx.post(
            f"{_API}/{settings.CLOUDINARY_CLOUD_NAME}/{resource_type}/upload",
            data=data,
            files={"file": (filename, content, content_type or "application/octet-stream")},
            timeout=45.0,
        )
        res.raise_for_status()
        body = res.json()
    except httpx.HTTPStatusError as exc:
        log.error("Cloudinary rejected %s: %s", filename, exc.response.text[:300])
        return None
    except Exception as exc:  # pragma: no cover - network dependent
        log.error("Cloudinary upload of %s failed: %s", filename, exc)
        return None

    return {
        "url": body.get("secure_url"),
        "public_id": body.get("public_id"),
        "bytes": body.get("bytes"),
        "format": body.get("format"),
    }


def destroy(public_id: str | None, resource_type: ResourceType = "image") -> bool:
    """Remove a previously uploaded asset. Safe to call with None."""
    if not public_id or not settings.cloudinary_enabled:
        return False
    timestamp = str(int(time.time()))
    params = {"public_id": public_id, "timestamp": timestamp}
    try:
        res = httpx.post(
            f"{_API}/{settings.CLOUDINARY_CLOUD_NAME}/{resource_type}/destroy",
            data={
                **params,
                "api_key": settings.CLOUDINARY_CLOUD_API_KEY,
                "signature": _sign(params),
            },
            timeout=20.0,
        )
        return res.json().get("result") == "ok"
    except Exception as exc:  # pragma: no cover
        log.warning("Cloudinary destroy of %s failed: %s", public_id, exc)
        return False


def upload_avatar(content: bytes, user_id: str, content_type: str) -> dict | None:
    return upload(
        content,
        filename=f"{user_id}.jpg",
        folder="avatars",
        resource_type="image",
        public_id=user_id,
        content_type=content_type,
    )


def is_publicly_deliverable(url: str | None) -> bool:
    """Cloudinary accounts block PDF delivery by default ("deny or ACL failure").

    A single HEAD tells us whether the CDN link can be shared directly, so the app
    upgrades itself to the CDN URL the moment that setting is turned on.
    """
    if not url:
        return False
    try:
        res = httpx.head(url, timeout=8.0, follow_redirects=True)
        return res.status_code == 200
    except Exception:
        return False


def upload_report_pdf(content: bytes, report_id: str, title: str) -> dict | None:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in title).strip("-")[:48] or "report"
    return upload(
        content,
        filename=f"DADAS-{safe}.pdf",
        folder="reports",
        resource_type="raw",
        public_id=f"{report_id}",
        content_type="application/pdf",
    )
