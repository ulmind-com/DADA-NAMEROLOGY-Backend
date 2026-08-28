from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import admin_user, superadmin_user
from app.core.security import hash_password
from app.db.session import get_db
from app.models import AuditLog, Report, ReportType, Role, Rule, User
from app.numerology import rules as rulestore
from app.schemas.admin import (
    AdminCreateIn,
    AdminUserUpdateIn,
    BroadcastIn,
    RuleUpsertIn,
    SettingIn,
)
from app.services.email import send_email
from app.services.pdf import build_report_pdf
from app.services.settings_store import all_settings, set_setting

router = APIRouter(prefix="/admin", tags=["admin"])


def _now() -> datetime:
    return datetime.now(UTC)


def _audit(db: Session, actor: User, action: str, target: str = "", meta: dict | None = None, note: str = ""):
    db.add(AuditLog(actor_id=actor.id, actor_email=actor.email, action=action,
                    target=target, meta=meta or {}, note=note))
    db.commit()


def _provider(u: User) -> str:
    if u.google_id and u.hashed_password:
        return "google+password"
    if u.google_id:
        return "google"
    return "password"


# ------------------------------------------------------------------- DASHBOARD
@router.get("/stats", summary="Dashboard metrics")
def stats(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    now = _now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = day_start - timedelta(days=6)
    month_start = day_start - timedelta(days=29)

    users_total = db.scalar(select(func.count(User.id))) or 0
    users_today = db.scalar(select(func.count(User.id)).where(User.created_at >= day_start)) or 0
    users_week = db.scalar(select(func.count(User.id)).where(User.created_at >= week_start)) or 0
    premium = db.scalar(select(func.count(User.id)).where(User.is_premium.is_(True))) or 0
    reports_total = db.scalar(select(func.count(Report.id))) or 0
    reports_today = db.scalar(select(func.count(Report.id)).where(Report.created_at >= day_start)) or 0

    by_type = {t.value: 0 for t in ReportType}
    for t, c in db.execute(select(Report.type, func.count(Report.id)).group_by(Report.type)):
        by_type[t.value if hasattr(t, "value") else str(t)] = c

    def series(model, since):
        rows = db.scalars(select(model.created_at).where(model.created_at >= since)).all()
        buckets = Counter(
            (d if d.tzinfo else d.replace(tzinfo=UTC)).strftime("%Y-%m-%d") for d in rows
        )
        out = []
        for i in range(30):
            day = (month_start + timedelta(days=i)).strftime("%Y-%m-%d")
            out.append({"date": day, "count": buckets.get(day, 0)})
        return out

    top_numbers = [
        {"number": int(n), "count": c}
        for n, c in db.execute(
            select(Report.score, func.count(Report.id))
            .where(Report.type == ReportType.name)
            .group_by(Report.score)
            .order_by(func.count(Report.id).desc())
            .limit(9)
        )
        if n is not None
    ]

    recent_users = [
        {"id": u.id, "email": u.email, "full_name": u.full_name, "provider": _provider(u),
         "is_premium": u.is_premium, "created_at": u.created_at}
        for u in db.scalars(select(User).order_by(User.created_at.desc()).limit(8))
    ]
    recent_reports = [
        {"id": r.id, "type": r.type.value, "title": r.title, "subtitle": r.subtitle,
         "score": r.score, "created_at": r.created_at,
         "user_email": r.user.email if r.user else None}
        for r in db.scalars(select(Report).order_by(Report.created_at.desc()).limit(8))
    ]

    return {
        "users_total": users_total, "users_today": users_today, "users_week": users_week,
        "premium_users": premium, "reports_total": reports_total, "reports_today": reports_today,
        "reports_by_type": by_type,
        "signups_series": series(User, month_start),
        "reports_series": series(Report, month_start),
        "top_numbers": top_numbers,
        "recent_users": recent_users, "recent_reports": recent_reports,
    }


# ----------------------------------------------------------------------- USERS
@router.get("/users", summary="List / search users")
def list_users(
    q: str | None = None,
    role: str | None = None,
    premium: bool | None = None,
    active: bool | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(admin_user),
):
    stmt = select(User)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(User.email).like(like),
                              func.lower(User.full_name).like(like),
                              User.phone.like(like)))
    if role:
        stmt = stmt.where(User.role == Role(role))
    if premium is not None:
        stmt = stmt.where(User.is_premium.is_(premium))
    if active is not None:
        stmt = stmt.where(User.is_active.is_(active))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(User.created_at.desc()).offset((page - 1) * size).limit(size)).all()
    counts = dict(db.execute(select(Report.user_id, func.count(Report.id)).group_by(Report.user_id)).all())

    return {
        "total": total, "page": page, "size": size, "pages": max(1, -(-total // size)),
        "items": [
            {
                "id": u.id, "email": u.email, "full_name": u.full_name, "phone": u.phone,
                "role": u.role.value, "is_active": u.is_active, "is_premium": u.is_premium,
                "is_email_verified": u.is_email_verified, "provider": _provider(u),
                "avatar_url": u.avatar_url, "dob": u.dob, "gender": u.gender,
                "reports_count": counts.get(u.id, 0),
                "created_at": u.created_at, "last_login_at": u.last_login_at,
            }
            for u in rows
        ],
    }


@router.get("/users/{user_id}", summary="One user with their report history")
def get_user(user_id: str, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    reports = db.scalars(
        select(Report).where(Report.user_id == u.id).order_by(Report.created_at.desc()).limit(50)
    ).all()
    return {
        "user": {
            "id": u.id, "email": u.email, "full_name": u.full_name, "phone": u.phone,
            "role": u.role.value, "is_active": u.is_active, "is_premium": u.is_premium,
            "is_email_verified": u.is_email_verified, "provider": _provider(u),
            "avatar_url": u.avatar_url, "dob": u.dob, "birth_time": u.birth_time,
            "birth_place": u.birth_place, "gender": u.gender,
            "free_reports_used": u.free_reports_used,
            "created_at": u.created_at, "last_login_at": u.last_login_at,
        },
        "reports": [
            {"id": r.id, "type": r.type.value, "tier": r.tier, "title": r.title,
             "subtitle": r.subtitle, "score": r.score, "created_at": r.created_at}
            for r in reports
        ],
    }


@router.patch("/users/{user_id}", summary="Update a user (premium, active, role)")
def update_user(
    user_id: str,
    body: AdminUserUpdateIn,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_user),
):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    data = body.model_dump(exclude_unset=True)
    if "role" in data and data["role"]:
        if admin.role != Role.superadmin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a super-admin can change roles.")
        u.role = Role(data.pop("role"))
    for k, v in data.items():
        if v is not None:
            setattr(u, k, v)
    db.commit()
    _audit(db, admin, "user.update", u.email, data)
    return {"ok": True}


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a user")
def delete_user(user_id: str, db: Session = Depends(get_db), admin: User = Depends(superadmin_user)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    if u.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot delete your own account.")
    email = u.email
    db.delete(u)
    db.commit()
    _audit(db, admin, "user.delete", email)


@router.post("/admins", status_code=status.HTTP_201_CREATED, summary="Create an admin account")
def create_admin(body: AdminCreateIn, db: Session = Depends(get_db), admin: User = Depends(superadmin_user)):
    if db.scalars(select(User).where(User.email == body.email.lower())).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "That email already exists.")
    u = User(
        email=body.email.lower(), full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=Role(body.role), is_email_verified=True,
    )
    db.add(u)
    db.commit()
    _audit(db, admin, "admin.create", u.email, {"role": body.role})
    return {"id": u.id, "email": u.email}


# --------------------------------------------------------------------- REPORTS
@router.get("/reports", summary="Every report, filterable")
def admin_reports(
    q: str | None = None,
    type: ReportType | None = None,
    tier: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(admin_user),
):
    stmt = select(Report)
    if type:
        stmt = stmt.where(Report.type == type)
    if tier:
        stmt = stmt.where(Report.tier == tier)
    if q:
        stmt = stmt.where(func.lower(Report.title).like(f"%{q.lower()}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Report.created_at.desc()).offset((page - 1) * size).limit(size)).all()
    return {
        "total": total, "page": page, "size": size, "pages": max(1, -(-total // size)),
        "items": [
            {"id": r.id, "type": r.type.value, "tier": r.tier, "title": r.title,
             "subtitle": r.subtitle, "score": r.score, "created_at": r.created_at,
             "user_email": r.user.email if r.user else None,
             "user_name": r.user.full_name if r.user else None}
            for r in rows
        ],
    }


@router.get("/reports/{report_id}", summary="One report with its full engine output")
def admin_report(report_id: str, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    r = db.get(Report, report_id)
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    return {
        "id": r.id, "type": r.type.value, "tier": r.tier, "title": r.title,
        "subtitle": r.subtitle, "score": r.score, "payload": r.payload, "result": r.result,
        "created_at": r.created_at,
        "user": {"id": r.user.id, "email": r.user.email, "full_name": r.user.full_name} if r.user else None,
    }


@router.get("/reports/{report_id}/pdf", summary="Render any report as a PDF")
def admin_report_pdf(report_id: str, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    r = db.get(Report, report_id)
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    pdf = build_report_pdf(r.type.value, r.title, r.result, r.user.full_name if r.user else "")
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{r.type.value}-{r.id}.pdf"'})


# ----------------------------------------------------------------------- RULES
@router.get("/rules/{kind}", summary="compound_meanings | root_profiles | pair_meanings")
def get_rules(kind: str, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    base = {
        "compound_meanings": rulestore.all_compounds,
        "root_profiles": rulestore.all_root_profiles,
        "pair_meanings": rulestore.all_pairs,
    }.get(kind)
    if not base:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown rule set.")
    overrides = {r.key: r.data for r in db.scalars(select(Rule).where(Rule.kind == kind))}
    return {"kind": kind, "items": base(), "overridden": list(overrides.keys())}


@router.put("/rules", summary="Create or update one rule entry")
def upsert_rule(body: RuleUpsertIn, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    row = db.scalars(select(Rule).where(Rule.kind == body.kind, Rule.key == body.key)).first()
    if row:
        row.data = body.data
        row.updated_by = admin.id
    else:
        db.add(Rule(kind=body.kind, key=body.key, data=body.data, updated_by=admin.id))
    db.commit()
    reload_rules(db)
    _audit(db, admin, "rule.update", f"{body.kind}:{body.key}", body.data)
    return {"ok": True}


@router.delete("/rules/{kind}/{key}", summary="Revert one rule to the bundled default")
def delete_rule(kind: str, key: str, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    row = db.scalars(select(Rule).where(Rule.kind == kind, Rule.key == key)).first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No override for this key.")
    db.delete(row)
    db.commit()
    reload_rules(db)
    _audit(db, admin, "rule.revert", f"{kind}:{key}")
    return {"ok": True}


def reload_rules(db: Session) -> None:
    """Re-apply every DB override on top of the bundled JSON."""
    rulestore.invalidate()
    grouped: dict[str, dict[str, dict]] = {}
    for r in db.scalars(select(Rule)):
        grouped.setdefault(r.kind, {})[r.key] = r.data
    for kind, overrides in grouped.items():
        rulestore.apply_overrides(kind, overrides)


# -------------------------------------------------------------------- SETTINGS
@router.get("/settings", summary="All app settings")
def get_settings_(db: Session = Depends(get_db), _: User = Depends(admin_user)):
    return all_settings(db)


@router.put("/settings", summary="Update one app setting")
def put_setting(body: SettingIn, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    set_setting(db, body.key, body.value)
    _audit(db, admin, "setting.update", body.key, body.value)
    return {"ok": True}


# ----------------------------------------------------------------------- AUDIT
@router.get("/audit", summary="Admin action log")
def audit(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(admin_user),
):
    total = db.scalar(select(func.count(AuditLog.id))) or 0
    rows = db.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).offset((page - 1) * size).limit(size)
    ).all()
    return {
        "total": total, "page": page, "size": size,
        "items": [
            {"id": a.id, "actor_email": a.actor_email, "action": a.action, "target": a.target,
             "meta": a.meta, "created_at": a.created_at}
            for a in rows
        ],
    }


# ------------------------------------------------------------------- BROADCAST
@router.post("/broadcast", summary="Email all users")
def broadcast(
    body: BroadcastIn,
    db: Session = Depends(get_db),
    admin: User = Depends(superadmin_user),
):
    stmt = select(User).where(User.is_active.is_(True))
    if body.audience == "premium":
        stmt = stmt.where(User.is_premium.is_(True))
    elif body.audience == "free":
        stmt = stmt.where(User.is_premium.is_(False))
    users = db.scalars(stmt).all()
    html = (
        "<div style=\"font-family:Poppins,sans-serif;background:#FBF3E7;padding:28px\">"
        "<div style=\"max-width:520px;margin:auto;background:#FFFDF8;border:1px solid #EEDCC4;"
        "border-radius:20px;padding:28px\">"
        f"<h2 style=\"color:#B3441E;font-size:18px;margin:0 0 12px\">{body.subject}</h2>"
        f"<div style=\"color:#3A2A1E;font-size:14px;line-height:1.7\">{body.body}</div>"
        "</div></div>"
    )
    sent = sum(1 for u in users if send_email(u.email, body.subject, html, body.body))
    _audit(db, admin, "broadcast", body.audience, {"recipients": len(users), "sent": sent})
    return {"recipients": len(users), "sent": sent}
