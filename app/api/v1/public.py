"""Unauthenticated, token-signed access to a shared report.

Cloudinary blocks PDF delivery on new accounts, so a share link points here by
default. The token is a long-lived signed JWT, which keeps the URL unguessable and
lets every link be invalidated at once by rotating SECRET_KEY.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.security import decode_token
from app.db.mongo import DB, get_db
from app.services.pdf import build_report_pdf

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/reports/{report_id}", summary="Open a shared report (no sign-in needed)")
def shared_report(
    report_id: str,
    t: str = Query(..., description="Share token from POST /reports/{id}/share"),
    db: DB = Depends(get_db),
):
    payload = decode_token(t, "share")
    if not payload or payload.get("sub") != report_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This share link is invalid or has expired.")

    report = db.reports.get(report_id)
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This report is no longer available.")

    owner = db.users.get(report.user_id)
    pdf = build_report_pdf(
        report.type.value, report.title, report.result, owner.full_name if owner else ""
    )
    safe = "".join(c if c.isalnum() or c in "-_ " else "" for c in report.title).strip() or "report"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="DADAS-{report.type.value}-{safe}.pdf"',
            "Cache-Control": "public, max-age=3600",
        },
    )
