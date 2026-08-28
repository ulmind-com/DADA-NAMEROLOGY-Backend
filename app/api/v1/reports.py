from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db.session import get_db
from app.models import Report, ReportType, User
from app.services.pdf import build_report_pdf

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", summary="My reports (paginated)")
def list_reports(
    type: ReportType | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    stmt = select(Report).where(Report.user_id == user.id)
    if type:
        stmt = stmt.where(Report.type == type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Report.created_at.desc()).offset((page - 1) * size).limit(size)
    ).all()
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
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }


@router.get("/{report_id}", summary="Full stored report")
def get_report(report_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    r = db.get(Report, report_id)
    if not r or r.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    return {
        "id": r.id, "type": r.type.value, "tier": r.tier, "title": r.title,
        "subtitle": r.subtitle, "score": r.score, "payload": r.payload,
        "result": r.result, "created_at": r.created_at,
    }


@router.get("/{report_id}/pdf", summary="Download report as PDF")
def report_pdf(report_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    r = db.get(Report, report_id)
    if not r or r.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    pdf = build_report_pdf(r.type.value, r.title, r.result, user.full_name)
    safe = "".join(c if c.isalnum() or c in "-_ " else "" for c in r.title).strip() or "report"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="DADAS-{r.type.value}-{safe}.pdf"'},
    )


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a saved report")
def delete_report(report_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    r = db.get(Report, report_id)
    if not r or r.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    db.delete(r)
    db.commit()
