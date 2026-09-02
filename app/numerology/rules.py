"""Rule store.

Bundled JSON is the seed. The admin panel writes overrides into the DB, and
`apply_overrides()` merges them on top at request time — so the client can change
every meaning without a redeploy.
"""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

_lock = threading.RLock()
_cache: dict[str, dict] = {}


def _load(name: str) -> dict:
    with open(DATA_DIR / f"{name}.json", encoding="utf-8") as fh:
        return json.load(fh)


def _get(name: str) -> dict:
    with _lock:
        if name not in _cache:
            _cache[name] = _load(name)
        return _cache[name]


def invalidate() -> None:
    """Called by the admin API after a rule is edited."""
    with _lock:
        _cache.clear()


def apply_overrides(kind: str, overrides: dict[str, dict]) -> None:
    """Merge DB overrides into the in-memory rule set."""
    with _lock:
        base = deepcopy(_get(kind))
        for key, patch in overrides.items():
            base.setdefault(key, {})
            base[key].update(patch)
        _cache[kind] = base


# --------------------------------------------------------------- accessors
RATING_ORDER = {"excellent": 4, "good": 3, "average": 2, "caution": 1, "bad": 0}
RATING_COLOR = {
    "excellent": "#0E8F5E",
    "good": "#1E9E6A",
    "average": "#E0A32E",
    "caution": "#E07A2E",
    "bad": "#D24B4B",
}


def rating_color(rating: str) -> str:
    return RATING_COLOR.get(rating, "#E0A32E")


def is_favourable(rating: str) -> bool:
    return RATING_ORDER.get(rating, 2) >= 3


# ------------------------------------------------------- client master data
# These come straight from the client's spreadsheets and Word charts, extracted
# verbatim. They are the source of truth for what the app tells a user.

def name_chart(n: int) -> dict:
    """Client's Name Compound Chart, compound numbers 3-100."""
    return _get("name_chart").get(str(n), {})


def all_name_chart() -> dict:
    return _get("name_chart")


def name_root_short(n: int) -> str:
    """Client's one-line meaning for a single-digit name number (1-9)."""
    return _get("name_root_short").get(str(n), "")


def vehicle_master(n: int) -> dict:
    """Client's 1-99 vehicle master row."""
    return _get("vehicle_master").get(str(n), {})


def all_vehicle_master() -> dict:
    return _get("vehicle_master")


def vehicle_patterns() -> dict:
    """Client's master-number, repeated-digit and sequential-series tables."""
    return _get("vehicle_patterns")


def name_favourable(compound: int) -> bool:
    """Client's verdict: a name number is unfavourable only when the client's own
    chart marks it 'Avoid this name number'. Everything else is acceptable."""
    entry = name_chart(compound)
    if entry:
        return not entry.get("avoid", False)
    # compounds beyond the chart fall back to the reduced root's chart entry
    from .chaldean import reduce_to_root
    root_entry = name_chart(reduce_to_root(compound))
    return not root_entry.get("avoid", False)


def root_profile_client(n: int) -> dict:
    """Root-number profile sourced from the client's data: planet and element from
    the 1-99 master, friendly/avoid from the master, and the one-line name meaning."""
    m = vehicle_master(n)
    return {
        "number": n,
        "planet": m.get("planet", ""),
        "element": m.get("element", ""),
        "friendly": m.get("friendly", []),
        "enemy": m.get("avoid", []),
        "colors": m.get("vehicle_colors", []),
        "title": rules_short_title(n),
        "description": name_root_short(n),
    }


def rules_short_title(n: int) -> str:
    return f"Number {n}"


def mobile_total_meaning(n: int) -> str:
    return _get("mobile_total").get(str(n), "")


def mobile_combination(a: int, b: int) -> dict:
    """Client's benefic/neutral/malefic verdict for a digit pair (order-independent)."""
    key = f"{min(a, b)}{max(a, b)}"
    return _get("mobile_combinations").get(key, {})


def all_mobile_combinations() -> dict:
    return _get("mobile_combinations")


# Client's Universal Benefic Total (Mobile Numerology Notes, section 8)
MOBILE_TOTAL_CLASS = {
    1: "benefic", 3: "benefic", 5: "benefic", 6: "benefic",
    4: "malefic", 7: "malefic", 8: "malefic",
    2: "neutral", 9: "neutral",
}


# ------------------------------------------------------- business numerology
def business_compound(n: int) -> dict:
    """Client's Business Compound Data (1-99): stars, rating and the 'For Business' text."""
    return _get("business_compound").get(str(n), {})


def all_business_compound() -> dict:
    return _get("business_compound")


def business_master(n: int) -> dict:
    """Client's Business Name Numerology master row (1-99)."""
    return _get("business_master").get(str(n), {})


def all_business_master() -> dict:
    return _get("business_master")


def business_favourable(compound: int) -> bool:
    """Client marks quality with a star rating for roots 1-9 and with the wording of
    the 'For Business' text for compounds. Treat 'challenging'/'demanding' wording
    and 1-2 star entries as unfavourable."""
    entry = business_compound(compound)
    if not entry:
        return True
    stars = entry.get("stars") or 0
    if stars:
        return stars >= 3
    text = (entry.get("business_text") or "").lower()
    return not any(w in text for w in ("challenging", "demanding", "difficult", "unfavourable"))


def mobile_multiples(digit: int) -> dict:
    """Client's 'Multiple Numbers and Their Effects' entry for a repeated digit."""
    return _get("mobile_multiples").get(str(digit), {})


def mobile_multiple_rules() -> dict:
    return _get("mobile_multiples").get("_rules", {})


def mobile_points() -> list[str]:
    """Client's 'Points to Remember' checklist."""
    return _get("mobile_points").get("points", [])


# --------------------------------------------------------------- numeroscope
def number_compatibility(n: int) -> dict:
    """Client's Compatibility of Numbers table (lucky / enemy / neutral per number)."""
    return _get("mobile_compatibility").get(str(n), {})


def all_number_compatibility() -> dict:
    return {k: v for k, v in _get("mobile_compatibility").items() if not k.startswith("_")}


def ideal_grid() -> list[list[int]]:
    """Client's ideal numeroscope: 4 9 2 / 3 5 7 / 8 1 6."""
    return _get("mobile_compatibility").get("_ideal_grid", [[4, 9, 2], [3, 5, 7], [8, 1, 6]])


def compatibility_note() -> str:
    return _get("mobile_compatibility").get("_note", {}).get("star", "")


def good_compounds(root: int) -> dict:
    """Client's 'Good Compounds' for a benefic root (1, 3, 5, 6)."""
    return _get("mobile_good_compounds").get(str(root), {})


def all_good_compounds() -> dict:
    return _get("mobile_good_compounds")


def vehicle_summary() -> dict:
    """Client's 'Favorable vs Unfavorable Vehicle Numbers' summary lists."""
    return _get("vehicle_patterns").get("summary", {})


def benefic_combinations() -> dict:
    """Only the combinations the client classes as benefic."""
    return {
        k: v for k, v in _get("mobile_combinations").items()
        if v.get("rating") == "benefic"
    }
