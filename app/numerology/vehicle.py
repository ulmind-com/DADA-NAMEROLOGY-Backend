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
from .mobile import _verdict, pair_grid

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

    # The "running number" (the last numeric block) is what most practitioners weigh most.
    running = parts["digits"] or "".join(c for c in plate if c.isdigit())
    run_compound = sum(int(d) for d in running) if running else 0
    run_total = reduce_to_root(run_compound)

    grid = pair_grid(running) if len(running) > 1 else []
    grid_score = round(sum(g["score"] for g in grid) * 100 / (2 * len(grid))) if grid else 50

    rp_run = rules.root_profile(run_total)
    rp_full = rules.root_profile(full_total)

    score = round(grid_score * 0.5 + rules.RATING_ORDER.get(
        rules.compound_meaning(run_compound).get("rating", "average"), 2) * 12.5)

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
        "full_profile": {"number": full_total, "planet": rp_full.get("planet"), "title": rp_full.get("title")},
        "running_number": running,
        "compound": run_compound,
        "total": run_total,
        "chain": reduction_chain(run_compound),
        "compound_meaning": rules.compound_meaning(run_compound),
        "total_profile": {
            "number": run_total,
            "planet": rp_run.get("planet"),
            "title": rp_run.get("title"),
            "description": rp_run.get("description"),
            "colors": rp_run.get("colors", []),
        },
        "grid": grid,
        "grid_summary": {
            "good": sum(1 for g in grid if g["rating"] == "good"),
            "average": sum(1 for g in grid if g["rating"] == "average"),
            "bad": sum(1 for g in grid if g["rating"] == "bad"),
            "total_pairs": len(grid),
        },
        "safety_note": _safety_note(run_total),
        "colors": rp_run.get("colors", []),
        "avoid_colors": rp_run.get("avoid_colors", []),
    }

    if dob:
        radical = radical_number(dob.day)
        destiny = destiny_number(dob.day, dob.month, dob.year)
        rp_rad = rules.root_profile(radical)
        friendly, enemy = rp_rad.get("friendly", []), rp_rad.get("enemy", [])
        level = "friendly" if run_total in friendly else ("enemy" if run_total in enemy else "neutral")
        score += {"friendly": 12, "neutral": 0, "enemy": -18}[level]
        result["owner"] = {
            "dob": dob.isoformat(),
            "radical": radical,
            "destiny": destiny,
            "radical_planet": rp_rad.get("planet"),
            "match": {
                "level": level,
                "label": {"friendly": "Suits You", "neutral": "Neutral", "enemy": "Does Not Suit You"}[level],
                "color": {"friendly": "#1E9E6A", "neutral": "#E0A32E", "enemy": "#D24B4B"}[level],
                "note": (
                    f"The vehicle number totals to {run_total}; your radical number is {radical}. "
                    + {
                        "friendly": "A supportive match — the vehicle will feel lucky and travel will stay smooth.",
                        "neutral": "A neutral match — no special benefit and no particular obstruction.",
                        "enemy": "A conflicting match — expect frequent repairs, disputes and travel delays.",
                    }[level]
                ),
            },
        }

    result["score"] = max(0, min(100, int(score)))
    result["verdict"] = _verdict(result["score"])
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
    """Best 'running numbers' of a given length for this owner."""
    radical = radical_number(dob.day)
    friendly = rules.root_profile(radical).get("friendly", [])
    out = []
    start, end = 10 ** (length - 1), 10**length
    for n in range(start, end):
        s = str(n)
        compound = sum(int(d) for d in s)
        total = reduce_to_root(compound)
        if total not in friendly:
            continue
        meaning = rules.compound_meaning(compound)
        if not rules.is_favourable(meaning.get("rating", "average")):
            continue
        grid = pair_grid(s)
        if any(g["rating"] == "bad" for g in grid):
            continue
        gscore = round(sum(g["score"] for g in grid) * 100 / (2 * len(grid)))
        out.append({
            "number": s, "compound": compound, "total": total,
            "title": meaning.get("title", ""), "rating": meaning.get("rating"),
            "score": gscore,
        })
        if len(out) >= limit * 20:
            break
    out.sort(key=lambda x: (-x["score"], x["number"]))
    return out[:limit]
