from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import admin_user, superadmin_user
from app.core.security import hash_password
from app.db.mongo import DB, DESC, get_db
from app.models import AuditLog, ReportType, Role, Rule, User, utcnow
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
from app.services.storage import destroy

router = APIRouter(prefix="/admin", tags=["admin"])


def _now() -> datetime:
    return datetime.now(UTC)


def _audit(db: DB, actor: User, action: str, target: str = "", meta: dict | None = None, note: str = ""):
    db.audit.insert(
        AuditLog(
            actor_id=actor.id, actor_email=actor.email, action=action,
            target=target, meta=meta or {}, note=note,
        )
    )


def _users_by_id(db: DB, ids: list[str]) -> dict[str, User]:
    unique = list({i for i in ids if i})
    if not unique:
        return {}
    return {u.id: u for u in db.users.find({"_id": {"$in": unique}})}


# ------------------------------------------------------------------- DASHBOARD
@router.get("/stats", summary="Dashboard metrics")
def stats(db: DB = Depends(get_db), _: User = Depends(admin_user)):
    now = _now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = day_start - timedelta(days=6)
    month_start = day_start - timedelta(days=29)

    users_total = db.users.count()
    users_today = db.users.count({"created_at": {"$gte": day_start}})
    users_week = db.users.count({"created_at": {"$gte": week_start}})
    premium = db.users.count({"is_premium": True})
    reports_total = db.reports.count()
    reports_today = db.reports.count({"created_at": {"$gte": day_start}})

    by_type = {t.value: 0 for t in ReportType}
    for row in db.reports.aggregate([{"$group": {"_id": "$type", "n": {"$sum": 1}}}]):
        if row["_id"] in by_type:
            by_type[row["_id"]] = row["n"]

    def series(repo) -> list[dict]:
        """One bucket per day for the last 30 days, zero-filled."""
        counts = {
            row["_id"]: row["n"]
            for row in repo.aggregate(
                [
                    {"$match": {"created_at": {"$gte": month_start}}},
                    {
                        "$group": {
                            "_id": {
                                "$dateToString": {
                                    "format": "%Y-%m-%d",
                                    "date": "$created_at",
                                    "timezone": "UTC",
                                }
                            },
                            "n": {"$sum": 1},
                        }
                    },
                ]
            )
        }
        out = []
        for i in range(30):
            day = (month_start + timedelta(days=i)).strftime("%Y-%m-%d")
            out.append({"date": day, "count": counts.get(day, 0)})
        return out

    top_numbers = [
        {"number": int(row["_id"]), "count": row["n"]}
        for row in db.reports.aggregate(
            [
                {"$match": {"type": ReportType.name.value, "score": {"$ne": None}}},
                {"$group": {"_id": "$score", "n": {"$sum": 1}}},
                {"$sort": {"n": -1}},
                {"$limit": 9},
            ]
        )
    ]

    recent_users = [
        {"id": u.id, "email": u.email, "full_name": u.full_name, "provider": u.provider,
         "is_premium": u.is_premium, "created_at": u.created_at}
        for u in db.users.find(sort=[("created_at", DESC)], limit=8)
    ]
    recent_rows = db.reports.find(sort=[("created_at", DESC)], limit=8)
    owners = _users_by_id(db, [r.user_id for r in recent_rows])
    recent_reports = [
        {"id": r.id, "type": r.type.value, "title": r.title, "subtitle": r.subtitle,
         "score": r.score, "created_at": r.created_at,
         "user_email": owners[r.user_id].email if r.user_id in owners else None}
        for r in recent_rows
    ]

    return {
        "users_total": users_total, "users_today": users_today, "users_week": users_week,
        "premium_users": premium, "reports_total": reports_total, "reports_today": reports_today,
        "reports_by_type": by_type,
        "signups_series": series(db.users),
        "reports_series": series(db.reports),
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
    db: DB = Depends(get_db),
    _: User = Depends(admin_user),
):
    flt: dict = {}
    if q:
        needle = re.escape(q.strip())
        flt["$or"] = [
            {"email": {"$regex": needle, "$options": "i"}},
            {"full_name": {"$regex": needle, "$options": "i"}},
            {"phone": {"$regex": needle, "$options": "i"}},
        ]
    if role:
        flt["role"] = Role(role).value
    if premium is not None:
        flt["is_premium"] = premium
    if active is not None:
        flt["is_active"] = active

    total = db.users.count(flt)
    rows = db.users.find(flt, sort=[("created_at", DESC)], skip=(page - 1) * size, limit=size)

    counts = {
        row["_id"]: row["n"]
        for row in db.reports.aggregate(
            [
                {"$match": {"user_id": {"$in": [u.id for u in rows]}}},
                {"$group": {"_id": "$user_id", "n": {"$sum": 1}}},
            ]
        )
    }

    return {
        "total": total, "page": page, "size": size, "pages": max(1, -(-total // size)),
        "items": [
            {
                "id": u.id, "email": u.email, "full_name": u.full_name, "phone": u.phone,
                "role": u.role.value, "is_active": u.is_active, "is_premium": u.is_premium,
                "is_email_verified": u.is_email_verified, "provider": u.provider,
                "avatar_url": u.avatar_url, "dob": u.dob, "gender": u.gender,
                "reports_count": counts.get(u.id, 0),
                "created_at": u.created_at, "last_login_at": u.last_login_at,
            }
            for u in rows
        ],
    }


@router.get("/users/{user_id}", summary="One user with their report history")
def get_user(user_id: str, db: DB = Depends(get_db), _: User = Depends(admin_user)):
    u = db.users.get(user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    reports = db.reports.find({"user_id": u.id}, sort=[("created_at", DESC)], limit=50)
    return {
        "user": {
            "id": u.id, "email": u.email, "full_name": u.full_name, "phone": u.phone,
            "role": u.role.value, "is_active": u.is_active, "is_premium": u.is_premium,
            "is_email_verified": u.is_email_verified, "provider": u.provider,
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
    db: DB = Depends(get_db),
    admin: User = Depends(admin_user),
):
    u = db.users.get(user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "role" in data:
        if admin.role != Role.superadmin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a super-admin can change roles.")
        data["role"] = Role(data["role"]).value
    db.users.update(u.id, data)
    _audit(db, admin, "user.update", u.email, data)
    return {"ok": True}


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a user")
def delete_user(user_id: str, db: DB = Depends(get_db), admin: User = Depends(superadmin_user)):
    u = db.users.get(user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    if u.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot delete your own account.")

    destroy(u.avatar_public_id)
    for r in db.reports.find({"user_id": u.id, "pdf_public_id": {"$ne": None}}):
        destroy(r.pdf_public_id, resource_type="raw")
    db.delete_user_cascade(u.id)
    _audit(db, admin, "user.delete", u.email)


@router.post("/admins", status_code=status.HTTP_201_CREATED, summary="Create an admin account")
def create_admin(body: AdminCreateIn, db: DB = Depends(get_db), admin: User = Depends(superadmin_user)):
    if db.users.exists({"email": body.email.lower()}):
        raise HTTPException(status.HTTP_409_CONFLICT, "That email already exists.")
    u = db.users.insert(
        User(
            email=body.email.lower(), full_name=body.full_name,
            hashed_password=hash_password(body.password),
            role=Role(body.role), is_email_verified=True,
        )
    )
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
    db: DB = Depends(get_db),
    _: User = Depends(admin_user),
):
    flt: dict = {}
    if type:
        flt["type"] = type
    if tier:
        flt["tier"] = tier
    if q:
        flt["title"] = {"$regex": re.escape(q.strip()), "$options": "i"}

    total = db.reports.count(flt)
    rows = db.reports.find(flt, sort=[("created_at", DESC)], skip=(page - 1) * size, limit=size)
    owners = _users_by_id(db, [r.user_id for r in rows])

    return {
        "total": total, "page": page, "size": size, "pages": max(1, -(-total // size)),
        "items": [
            {"id": r.id, "type": r.type.value, "tier": r.tier, "title": r.title,
             "subtitle": r.subtitle, "score": r.score, "created_at": r.created_at,
             "pdf_url": r.pdf_url,
             "user_email": owners[r.user_id].email if r.user_id in owners else None,
             "user_name": owners[r.user_id].full_name if r.user_id in owners else None}
            for r in rows
        ],
    }


@router.get("/reports/{report_id}", summary="One report with its full engine output")
def admin_report(report_id: str, db: DB = Depends(get_db), _: User = Depends(admin_user)):
    r = db.reports.get(report_id)
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    owner = db.users.get(r.user_id)
    return {
        "id": r.id, "type": r.type.value, "tier": r.tier, "title": r.title,
        "subtitle": r.subtitle, "score": r.score, "payload": r.payload, "result": r.result,
        "pdf_url": r.pdf_url, "created_at": r.created_at,
        "user": {"id": owner.id, "email": owner.email, "full_name": owner.full_name} if owner else None,
    }


@router.get("/reports/{report_id}/pdf", summary="Render any report as a PDF")
def admin_report_pdf(report_id: str, db: DB = Depends(get_db), _: User = Depends(admin_user)):
    r = db.reports.get(report_id)
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    owner = db.users.get(r.user_id)
    pdf = build_report_pdf(r.type.value, r.title, r.result, owner.full_name if owner else "")
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{r.type.value}-{r.id}.pdf"'})


# ----------------------------------------------------------------------- RULES
@router.get("/rules/{kind}", summary="compound_meanings | root_profiles | pair_meanings")
def get_rules(kind: str, db: DB = Depends(get_db), _: User = Depends(admin_user)):
    base = {
        "compound_meanings": rulestore.all_compounds,
        "root_profiles": rulestore.all_root_profiles,
        "pair_meanings": rulestore.all_pairs,
    }.get(kind)
    if not base:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown rule set.")
    overrides = [r.key for r in db.rules.find({"kind": kind})]
    return {"kind": kind, "items": base(), "overridden": overrides}


@router.put("/rules", summary="Create or update one rule entry")
def upsert_rule(body: RuleUpsertIn, db: DB = Depends(get_db), admin: User = Depends(admin_user)):
    existing = db.rules.find_one({"kind": body.kind, "key": body.key})
    if existing:
        db.rules.update(
            existing.id, {"data": body.data, "updated_by": admin.id, "updated_at": utcnow()}
        )
    else:
        db.rules.insert(Rule(kind=body.kind, key=body.key, data=body.data, updated_by=admin.id))
    reload_rules(db)
    _audit(db, admin, "rule.update", f"{body.kind}:{body.key}", body.data)
    return {"ok": True}


@router.delete("/rules/{kind}/{key:path}", summary="Revert one rule to the bundled default")
def delete_rule(kind: str, key: str, db: DB = Depends(get_db), admin: User = Depends(admin_user)):
    row = db.rules.find_one({"kind": kind, "key": key})
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No override for this key.")
    db.rules.delete(row.id)
    reload_rules(db)
    _audit(db, admin, "rule.revert", f"{kind}:{key}")
    return {"ok": True}


def reload_rules(db: DB) -> None:
    """Re-apply every stored override on top of the bundled JSON."""
    rulestore.invalidate()
    grouped: dict[str, dict[str, dict]] = {}
    for r in db.rules.find():
        grouped.setdefault(r.kind, {})[r.key] = r.data
    for kind, overrides in grouped.items():
        rulestore.apply_overrides(kind, overrides)


# -------------------------------------------------------------------- SETTINGS
@router.get("/settings", summary="All app settings")
def get_settings_(db: DB = Depends(get_db), _: User = Depends(admin_user)):
    return all_settings(db)


@router.put("/settings", summary="Update one app setting")
def put_setting(body: SettingIn, db: DB = Depends(get_db), admin: User = Depends(admin_user)):
    set_setting(db, body.key, body.value)
    _audit(db, admin, "setting.update", body.key, body.value)
    return {"ok": True}


# ----------------------------------------------------------------------- AUDIT
@router.get("/audit", summary="Admin action log")
def audit(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: DB = Depends(get_db),
    _: User = Depends(admin_user),
):
    total = db.audit.count()
    rows = db.audit.find(sort=[("created_at", DESC)], skip=(page - 1) * size, limit=size)
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
    db: DB = Depends(get_db),
    admin: User = Depends(superadmin_user),
):
    flt: dict = {"is_active": True}
    if body.audience == "premium":
        flt["is_premium"] = True
    elif body.audience == "free":
        flt["is_premium"] = False

    users = db.users.find(flt)
    html = (
        '<div style="font-family:Poppins,sans-serif;background:#FBF3E7;padding:28px">'
        '<div style="max-width:520px;margin:auto;background:#FFFDF8;border:1px solid #EEDCC4;'
        'border-radius:20px;padding:28px">'
        f'<h2 style="color:#B3441E;font-size:18px;margin:0 0 12px">{body.subject}</h2>'
        f'<div style="color:#3A2A1E;font-size:14px;line-height:1.7">{body.body}</div>'
        "</div></div>"
    )
    sent = sum(1 for u in users if send_email(u.email, body.subject, html, body.body))
    _audit(db, admin, "broadcast", body.audience, {"recipients": len(users), "sent": sent})
    return {"recipients": len(users), "sent": sent}
