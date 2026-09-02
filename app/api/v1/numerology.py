from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import current_user, optional_user
from app.db.mongo import DB, get_db
from app.models import Report, ReportType, User
from app.numerology import rules
from app.numerology.chaldean import destiny_number, radical_number
from app.numerology.mobile import analyse_mobile, compare_numbers
from app.numerology.name import full_name_report, newborn_report, quick_name, suggest_corrections
from app.numerology.numeroscope import build as build_numeroscope
from app.numerology.numeroscope import recommend_mobile_total
from app.numerology.vehicle import analyse_vehicle, suggest_plate_numbers
from app.schemas.numerology import (
    AnalysisOut,
    MobileCompareIn,
    MobileIn,
    NameFullIn,
    NameQuickIn,
    NewBornIn,
    PlateSuggestIn,
    VehicleIn,
)
from app.services.settings_store import get_setting

router = APIRouter(prefix="/numerology", tags=["numerology"])


def _save(
    db: DB,
    user: User | None,
    rtype: ReportType,
    tier: str,
    title: str,
    subtitle: str,
    score: float | None,
    payload: dict,
    result: dict,
) -> Report | None:
    """Anonymous analyses are computed but not stored."""
    if not user:
        return None
    return db.reports.insert(
        Report(
            user_id=user.id, type=rtype, tier=tier, title=title, subtitle=subtitle,
            score=score, payload=payload, result=result,
        )
    )


def _require_quota(db: DB, user: User) -> None:
    if user.is_premium:
        return
    free_limit = int(get_setting(db, "free_full_reports", {"value": 1}).get("value", 1))
    if user.free_reports_used >= free_limit:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            "You have used your free detailed report. Upgrade to continue.",
        )


def _consume_quota(db: DB, user: User) -> None:
    if not user.is_premium:
        db.users.increment(user.id, "free_reports_used")


# ------------------------------------------------------------------ NAME (free)
@router.post("/name/quick", response_model=AnalysisOut, summary="Free name result")
def name_quick(
    body: NameQuickIn,
    db: DB = Depends(get_db),
    user: User | None = Depends(optional_user),
):
    result = quick_name(body.name, body.kind)
    rtype = ReportType.business if body.kind == "business" else ReportType.name
    report = _save(
        db, user, rtype, "free", body.name,
        f"Compound {result['compound']} · Total {result['total']}",
        float(result["total"]), body.model_dump(mode="json"), result,
    )
    return AnalysisOut(
        report_id=report.id if report else None, saved=bool(report), tier="free", result=result
    )


@router.post("/name/corrections", response_model=AnalysisOut, summary="Suggested spelling corrections")
def name_corrections(body: NameQuickIn, user: User = Depends(current_user)):
    """Correction candidates ranked against the user's own birth numbers when known."""
    radical = destiny = None
    if user.dob:
        radical = radical_number(user.dob.day)
        destiny = destiny_number(user.dob.day, user.dob.month, user.dob.year)
    suggestions = suggest_corrections(body.name, radical=radical, destiny=destiny, limit=12)
    return AnalysisOut(tier="premium" if user.is_premium else "free", result={"suggestions": suggestions})


# ------------------------------------------------------------- NAME (full/paid)
@router.post("/name/full", response_model=AnalysisOut, summary="Detailed name report")
def name_full(
    body: NameFullIn,
    db: DB = Depends(get_db),
    user: User = Depends(current_user),
):
    if not body.accept_terms:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Please accept the terms & conditions.")
    _require_quota(db, user)
    result = full_name_report(body.name, body.dob, body.gender or "", body.kind)
    rtype = ReportType.business if body.kind == "business" else ReportType.name
    report = _save(
        db, user, rtype, "premium", body.name,
        f"Compound {result['compound']} · Total {result['total']} · {result['alignment_score']}% aligned",
        float(result["alignment_score"]), body.model_dump(mode="json"), result,
    )
    _consume_quota(db, user)
    return AnalysisOut(report_id=report.id if report else None, saved=bool(report), tier="premium", result=result)


@router.post("/newborn", response_model=AnalysisOut, summary="New born name guidance")
def newborn(
    body: NewBornIn,
    db: DB = Depends(get_db),
    user: User | None = Depends(optional_user),
):
    result = newborn_report(body.dob, body.time or "", body.place or "", body.gender or "")
    report = _save(
        db, user, ReportType.newborn, "free", f"New born · {body.dob.isoformat()}",
        f"Radical {result['radical']['number']} · Destiny {result['destiny']['number']}",
        float(result["destiny"]["number"]), body.model_dump(mode="json"), result,
    )
    return AnalysisOut(report_id=report.id if report else None, saved=bool(report), result=result)


# ---------------------------------------------------------------------- MOBILE
@router.post("/mobile", response_model=AnalysisOut, summary="Mobile number analysis + TOTAL GRID")
def mobile(
    body: MobileIn,
    db: DB = Depends(get_db),
    user: User | None = Depends(optional_user),
):
    dob = body.dob or (user.dob if user else None)
    result = analyse_mobile(body.number, dob, body.name or (user.full_name if user else ""))
    if not result["valid"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Please enter a valid mobile number.")
    report = _save(
        db, user, ReportType.mobile, "free", result["formatted"],
        f"Compound {result['compound']} · Total {result['total']} · {result['score']}%",
        float(result["score"]), body.model_dump(mode="json"), result,
    )
    return AnalysisOut(report_id=report.id if report else None, saved=bool(report), result=result)


@router.post("/mobile/compare", response_model=AnalysisOut, summary="Check / choose a new number")
def mobile_compare(
    body: MobileCompareIn,
    user: User | None = Depends(optional_user),
):
    dob = body.dob or (user.dob if user else None)
    cur = analyse_mobile(body.current, dob, body.name or "")
    cand = analyse_mobile(body.candidate, dob, body.name or "")
    return AnalysisOut(result={"current": cur, "candidate": cand, "comparison": compare_numbers(cur, cand)})


# --------------------------------------------------------------------- VEHICLE
@router.post("/vehicle", response_model=AnalysisOut, summary="Vehicle registration analysis")
def vehicle(
    body: VehicleIn,
    db: DB = Depends(get_db),
    user: User | None = Depends(optional_user),
):
    dob = body.dob or (user.dob if user else None)
    result = analyse_vehicle(
        body.registration, dob, body.vehicle_type, body.owner_name or (user.full_name if user else "")
    )
    report = _save(
        db, user, ReportType.vehicle, "free", result["formatted"],
        f"Total {result['total']} · {result['score']}%",
        float(result["score"]), body.model_dump(mode="json"), result,
    )
    return AnalysisOut(report_id=report.id if report else None, saved=bool(report), result=result)


@router.post("/vehicle/suggest", response_model=AnalysisOut, summary="Best running numbers for a plate")
def vehicle_suggest(body: PlateSuggestIn):
    return AnalysisOut(result={"suggestions": suggest_plate_numbers(body.dob, body.length)})


# ----------------------------------------------------------------- REFERENCE
@router.get("/reference/numbers", summary="Client's 1-9 root profiles (planet, element, colours, friends)")
def reference_numbers():
    return {str(n): rules.root_profile_client(n) for n in range(1, 10)}


@router.get("/reference/name-chart", summary="Client's Name Compound Chart (3-100)")
def reference_name_chart():
    return rules.all_name_chart()


@router.get("/reference/vehicle", summary="Client's 1-99 vehicle master")
def reference_vehicle():
    return rules.all_vehicle_master()


@router.get("/reference/mobile-combinations", summary="Client's mobile digit-pair combinations")
def reference_mobile_combinations():
    return rules.all_mobile_combinations()


@router.post("/numeroscope", response_model=AnalysisOut, summary="Numeroscope grid + lucky/unlucky numbers")
def numeroscope(body: NewBornIn):
    """The client's numeroscope: the 3x3 grid built from the date of birth, with the
    missing, lucky, unlucky and neutral numbers derived from their compatibility table."""
    return AnalysisOut(result=build_numeroscope(body.dob))


@router.post("/mobile/recommend", response_model=AnalysisOut,
             summary="Which mobile total to aim for (client's finalising method)")
def mobile_recommend(body: NewBornIn):
    """Runs the client's 'Finalizing a beneficial mobile number' steps: benefic
    totals absent from the grid that are also compatible with Mulank and Bhagyank."""
    return AnalysisOut(result=recommend_mobile_total(body.dob))


@router.get("/reference/vehicle-summary", summary="Client's favourable / caution vehicle numbers")
def reference_vehicle_summary():
    return rules.vehicle_summary()


@router.get("/reference/compatibility", summary="Client's Compatibility of Numbers table")
def reference_compatibility():
    return {
        "table": rules.all_number_compatibility(),
        "ideal_grid": rules.ideal_grid(),
        "note": rules.compatibility_note(),
    }


@router.get("/reference/good-compounds", summary="Client's Good Compounds per benefic root")
def reference_good_compounds():
    return rules.all_good_compounds()


@router.get("/reference/mobile-points", summary="Client's Points to Remember checklist")
def reference_mobile_points():
    return {"points": rules.mobile_points(), "multiple_rules": rules.mobile_multiple_rules()}


@router.get("/reference/business", summary="Client's business numerology database (1-99)")
def reference_business():
    master = rules.all_business_master()
    compound = rules.all_business_compound()
    return {
        k: {**master.get(k, {}), **compound.get(k, {})}
        for k in sorted(set(master) | set(compound), key=int)
    }
