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
def root_profile(n: int) -> dict:
    return _get("root_profiles").get(str(n), {})


def all_root_profiles() -> dict:
    return _get("root_profiles")


def compound_meaning(n: int) -> dict:
    table = _get("compound_meanings")
    if str(n) in table:
        return table[str(n)]
    # beyond 52 -> fall back to the reduced root
    from .chaldean import reduce_to_root

    return table.get(str(reduce_to_root(n)), {
        "title": "", "rating": "average", "short": "", "description": "",
    })


def pair_meaning(a: int, b: int) -> dict:
    return _get("pair_meanings").get(f"{a}:{b}", {
        "pair": f"{a}:{b}", "rating": "average", "label": "Average",
        "color": "#E0A32E", "score": 1, "impact": "", "planets": "",
    })


def all_pairs() -> dict:
    return _get("pair_meanings")


def all_compounds() -> dict:
    return _get("compound_meanings")


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
