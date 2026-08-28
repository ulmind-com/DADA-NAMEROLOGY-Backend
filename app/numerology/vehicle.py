"""Vehicle-number numerology (registration plates).

The client's rules for this sheet are still pending, so the engine is built on the
same verified Chaldean base as Name + Mobile and every text it emits comes from the
editable rule store. When the final rules arrive only the rule JSON needs updating.
"""

from __future__ import annotations

import re
from datetime import date

from . import rules
from .chaldean import destiny_number, letter_value, radical_number, reduce_to_root, reduction_chain
from .mobile import _verdict

_CLEAN = re.compile(r"[^A-Z0-9]+")

# Indian plate: WB 06 AB 1234  -> state / rto / series / number
_PLATE = re.compile(r"^([A-Z]{2})(\d{1,2})([A-Z]{0,3})(\d{1,4})$")

VEHICLE_TYPES = ["car", "bike", "commercial", "other"]


def clean_plate(raw: str) -> str:
    return _CLEAN.sub("", (raw or "").upper())


def parse_plate(plate: str) -> dict:
    m = _PLATE.match(plate)
    if not m:
        return {"structured": False, "state": "", "rto": "", "series": "", "digits": ""}
    state, rto, series, digits = m.groups()
    return {
        "structured": True,
        "state": state,
        "rto": rto,
        "series": series,
        "digits": digits,
    }


def _grade_to_verdict(grade: str, score: int) -> dict:
    """Map the client's rating grade to the app's verdict shape."""
    g = (grade or "").lower()
    if "excellent" in g:
        return {"level": "excellent", "label": "Excellent Number", "color": "#0E8F5E"}
    if "very good" in g:
        return {"level": "good", "label": "Very Good Number", "color": "#1E9E6A"}
    if "good" in g:
        return {"level": "good", "label": "Good Number", "color": "#1E9E6A"}
    if "neutral" in g or "average" in g:
        return {"level": "average", "label": "Neutral Number", "color": "#E0A32E"}
    if "poor" in g or "bad" in g or "avoid" in g:
        return {"level": "bad", "label": "Not Recommended", "color": "#D24B4B"}
    return _verdict(score)


def _master_or_repeat(running: str) -> dict | None:
    """Client's special-pattern note for master numbers and repeated double digits."""
    patterns = rules.vehicle_patterns()
    total_compound = sum(int(d) for d in running) if running else 0
    # master numbers 11, 22, 33 (the compound itself, unreduced)
    key = str(total_compound)
    if key in patterns.get("master", {}):
        m = patterns["master"][key]
        return {"kind": "Master Number", "number": key, **m}
    # repeated double digits like 44, 55 ... appearing in the running number
    for rep, meta in patterns.get("repeated", {}).items():
        if rep in running:
            return {"kind": "Repeated Digits", "number": rep, **meta}
    return None


def analyse_vehicle(
    registration: str,
    dob: date | None = None,
    vehicle_type: str = "car",
    owner_name: str = "",
) -> dict:
    plate = clean_plate(registration)
    parts = parse_plate(plate)

    breakdown = []
    for ch in plate:
        val = int(ch) if ch.isdigit() else letter_value(ch)
        breakdown.append({"char": ch, "value": val, "type": "digit" if ch.isdigit() else "letter"})

    full_compound = sum(b["value"] for b in breakdown)
    full_total = reduce_to_root(full_compound)

    # The running number (last numeric block) is what the client's chart scores.
    running = parts["digits"] or "".join(c for c in plate if c.isdigit())
    run_compound = sum(int(d) for d in running) if running else 0
    run_total = reduce_to_root(run_compound)

    # Look the compound up in the client's 1-99 master. Beyond 99, reduce to the
    # root and use that row.
    master = rules.vehicle_master(run_compound) or rules.vehicle_master(run_total)

    score = int(master.get("score") or 50)
    grade = master.get("grade", "")
    friendly = master.get("friendly", [])
    avoid = master.get("avoid", [])

    # Master-number / repeated-digit patterns can lift or temper the base score.
    pattern = _master_or_repeat(running)
    if pattern and pattern.get("score"):
        score = round((score + int(pattern["score"])) / 2)

    result: dict = {
        "input": registration,
        "registration": plate,
        "formatted": _format_plate(parts, plate),
        "vehicle_type": vehicle_type,
        "owner_name": owner_name,
        "parts": parts,
        "breakdown": breakdown,
        "full_compound": full_compound,
        "full_total": full_total,
        "full_profile": {"number": full_total, "planet": rules.vehicle_master(full_total).get("planet", "")},
        "running_number": running,
        "compound": run_compound,
        "total": run_total,
        "chain": reduction_chain(run_compound),
        "compound_meaning": {
            "title": f"Number {run_compound}",
            "rating": grade.lower() or "average",
            "short": master.get("summary", ""),
            "description": master.get("attributes", "") or master.get("summary", ""),
        },
        "total_profile": {
            "number": run_compound if run_compound <= 99 else run_total,
            "planet": master.get("planet", ""),
            "element": master.get("element", ""),
            "title": master.get("grade", ""),
            "description": master.get("summary", ""),
            "colors": master.get("vehicle_colors", []),
        },
        "vehicle_types": master.get("vehicle_types", []),
        "best_use": master.get("best_use", ""),
        "friendly_numbers": friendly,
        "avoid_numbers": avoid,
        "grade": grade,
        "grid": [],
        "grid_summary": {"good": 0, "average": 0, "bad": 0, "total_pairs": 0},
        "safety_note": _safety_note(run_total),
        "colors": master.get("vehicle_colors", []),
        "avoid_colors": [],
        "pattern": pattern,
    }

    if dob:
        radical = radical_number(dob.day)
        destiny = destiny_number(dob.day, dob.month, dob.year)
        level = "friendly" if radical in friendly else ("enemy" if radical in avoid else "neutral")
        score += {"friendly": 8, "neutral": 0, "enemy": -15}[level]
        result["owner"] = {
            "dob": dob.isoformat(),
            "radical": radical,
            "destiny": destiny,
            "radical_planet": rules.vehicle_master(radical).get("planet", ""),
            "match": {
                "level": level,
                "label": {"friendly": "Suits You", "neutral": "Neutral", "enemy": "Does Not Suit You"}[level],
                "color": {"friendly": "#1E9E6A", "neutral": "#E0A32E", "enemy": "#D24B4B"}[level],
                "note": (
                    f"This number's friendly owner roots are {friendly or '—'} and it advises "
                    f"avoiding {avoid or '—'}. Your radical number is {radical}, which "
                    + {
                        "friendly": "is friendly — a supportive match.",
                        "neutral": "is neutral — no special benefit or obstruction.",
                        "enemy": "is on the avoid list — a conflicting match.",
                    }[level]
                ),
            },
        }

    result["score"] = max(0, min(100, int(score)))
    result["verdict"] = _grade_to_verdict(grade, result["score"])
    result["recommendations"] = _recommendations(result)
    return result


def _format_plate(parts: dict, plate: str) -> str:
    if not parts["structured"]:
        return plate
    return " ".join(p for p in [parts["state"], parts["rto"], parts["series"], parts["digits"]] if p)


def _safety_note(total: int) -> str:
    notes = {
        1: "Confident driving. Avoid overtaking out of ego.",
        2: "Calm, comfortable rides. Stay alert on night journeys.",
        3: "Fortunate for long-distance travel and family trips.",
        4: "Sudden mechanical faults are possible — service the vehicle on schedule.",
        5: "Fast and agile. Keep an eye on speed; it invites challans.",
        6: "Comfort-oriented and smooth. Excellent for family and luxury vehicles.",
        7: "Good for long solo journeys; keep the paperwork always inside the vehicle.",
        8: "Delays, fines and heavy repair bills are common. Never skip insurance.",
        9: "High speed and high energy — accident risk if the temper is not controlled.",
    }
    return notes.get(total, "")


def _recommendations(r: dict) -> list[str]:
    out = []
    bad = [g for g in r["grid"] if g["rating"] == "bad"]
    if bad:
        out.append("Weak digit pairs in the running number: " + ", ".join(g["pair"] for g in bad) + ".")
    if r["colors"]:
        out.append("Favourable vehicle colours: " + ", ".join(r["colors"]) + ".")
    if r["avoid_colors"]:
        out.append("Colours to avoid: " + ", ".join(r["avoid_colors"]) + ".")
    if r["safety_note"]:
        out.append(r["safety_note"])
    if r["score"] < 45:
        out.append("If the registration is not final yet, choose a plate whose running number totals to one of your friendly numbers.")
    return out


def suggest_plate_numbers(dob: date, length: int = 4, limit: int = 12) -> list[dict]:
    """Best running numbers for this owner, scored by the client's 1-99 master."""
    radical = radical_number(dob.day)
    out = []
    start, end = 10 ** (length - 1), 10**length
    for n in range(start, end):
        s = str(n)
        compound = sum(int(d) for d in s)
        master = rules.vehicle_master(compound) or rules.vehicle_master(reduce_to_root(compound))
        if not master:
            continue
        # the owner's radical must be friendly (and not on the avoid list) for this number
        if radical in master.get("avoid", []):
            continue
        if radical not in master.get("friendly", []):
            continue
        score = int(master.get("score") or 0)
        if score < 70:
            continue
        out.append({
            "number": s, "compound": compound, "total": reduce_to_root(compound),
            "title": master.get("grade", ""), "rating": master.get("grade", "").lower(),
            "score": score, "colors": master.get("vehicle_colors", []),
        })
        if len(out) >= limit * 30:
            break
    out.sort(key=lambda x: (-x["score"], x["number"]))
    return out[:limit]
