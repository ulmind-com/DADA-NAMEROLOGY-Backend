from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.api.deps import current_user
from app.core.security import create_share_token
from app.db.mongo import DB, DESC, get_db
from app.models import Report, ReportType, User
from app.services.pdf import build_report_pdf
from app.services.storage import destroy, is_publicly_deliverable, upload_report_pdf

router = APIRouter(prefix="/reports", tags=["reports"])


def _owned(db: DB, report_id: str, user: User) -> Report:
    r = db.reports.get(report_id)
    if not r or r.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    return r


@router.get("", summary="My reports (paginated)")
def list_reports(
    type: ReportType | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: DB = Depends(get_db),
    user: User = Depends(current_user),
):
    flt: dict = {"user_id": user.id}
    if type:
        flt["type"] = type
    total = db.reports.count(flt)
    rows = db.reports.find(
        flt, sort=[("created_at", DESC)], skip=(page - 1) * size, limit=size
    )
    return {
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, -(-total // size)),
        "items": [
            {
                "id": r.id,
                "type": r.type.value,
                "tier": r.tier,
                "title": r.title,
                "subtitle": r.subtitle,
                "score": r.score,
                "pdf_url": r.pdf_url,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }


@router.get("/{report_id}", summary="Full stored report")
def get_report(report_id: str, db: DB = Depends(get_db), user: User = Depends(current_user)):
    r = _owned(db, report_id, user)
    return {
        "id": r.id, "type": r.type.value, "tier": r.tier, "title": r.title,
        "subtitle": r.subtitle, "score": r.score, "payload": r.payload,
        "result": r.result, "pdf_url": r.pdf_url, "created_at": r.created_at,
    }


@router.get("/{report_id}/pdf", summary="Download report as PDF")
def report_pdf(report_id: str, db: DB = Depends(get_db), user: User = Depends(current_user)):
    r = _owned(db, report_id, user)
    pdf = build_report_pdf(r.type.value, r.title, r.result, user.full_name)
    safe = "".join(c if c.isalnum() or c in "-_ " else "" for c in r.title).strip() or "report"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="DADAS-{r.type.value}-{safe}.pdf"'},
    )


@router.post("/{report_id}/share", summary="Get a shareable PDF link")
def share_report(
    report_id: str,
    request: Request,
    db: DB = Depends(get_db),
    user: User = Depends(current_user),
):
    """A link anyone can open — for WhatsApp, email or a printout.

    The PDF is archived to Cloudinary on the first call. Cloudinary blocks PDF
    delivery on new accounts, so the shared link points at this API's public
    endpoint; once "PDF and ZIP files delivery" is enabled in the Cloudinary
    console the CDN link is handed out instead, with no code change.
    """
    r = _owned(db, report_id, user)
    cached = bool(r.pdf_url)

    if not cached:
        pdf = build_report_pdf(r.type.value, r.title, r.result, user.full_name)
        uploaded = upload_report_pdf(pdf, r.id, r.title)
        if uploaded:
            db.reports.update(
                r.id, {"pdf_url": uploaded["url"], "pdf_public_id": uploaded["public_id"]}
            )
            r.pdf_url = uploaded["url"]

    if is_publicly_deliverable(r.pdf_url):
        return {"url": r.pdf_url, "cdn_url": r.pdf_url, "source": "cloudinary", "cached": cached}

    base = str(request.base_url).rstrip("/")
    token = create_share_token(r.id)
    return {
        "url": f"{base}{request.scope.get('root_path', '')}/api/v1/public/reports/{r.id}?t={token}",
        "cdn_url": r.pdf_url,
        "source": "api",
        "cached": cached,
    }


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a saved report")
def delete_report(report_id: str, db: DB = Depends(get_db), user: User = Depends(current_user)):
    r = _owned(db, report_id, user)
    destroy(r.pdf_public_id, resource_type="raw")
    db.reports.delete(r.id)
