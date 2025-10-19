# app/utils/comp_sort.py
from typing import Any, Optional

# --- helpers to read from dicts or ORM objects ---
def _val(x: Any, name: str):
    if isinstance(x, dict):
        return x.get(name)
    return getattr(x, name, None)

# --- priorities copied from competitions.py ---
_CUP_ORDER = {
    "national cup": 0, "league cup": 1, "super cup": 2, "domestic cup": 3,
    "state cup": 4, "amateur cup": 5, "commemorative": 6,
}

def _cup_rank_priority(s: Optional[str]) -> int:
    return _CUP_ORDER.get((s or "").strip().lower(), 999)

def _gender_priority(s: Optional[str]) -> int:
    v = (s or "").strip().lower()
    if v in ("m", "men", "male"): return 0
    if v in ("w", "women", "female"): return 1
    return 2

def _age_priority(s: Optional[str]) -> int:
    v = (s or "").strip().lower()
    if v in ("senior", "open"): return 0
    if v in ("youth", "u23", "u21", "u20", "u19", "u18", "u17", "u16", "u15"): return 1
    return 2

def _type_priority(t: Optional[str]) -> int:
    v = (t or "").strip().lower()
    if v == "league": return 0
    if v == "cup": return 1
    return 2  # qualifiers/other

def _domestic_bucket(x: Any) -> int:
    """
    0 = Clubs, 1 = National Teams, 2 = Qualifiers
    """
    t = (_val(x, "type") or "").strip().lower()
    cr = (_val(x, "cup_rank") or "").strip().lower()
    if t in ("qualifier", "qualifiers", "qualification"):
        return 2
    if cr in ("national teams", "national_team", "national-teams", "nt"):
        return 1
    if cr in ("clubs", "club") or t == "league":
        return 0
    return 0

def _league_metric(x: Any) -> int:
    v = _val(x, "tier")
    try:
        return int(v) if v is not None else 9999
    except Exception:
        return 9999

def _cup_metric(x: Any) -> int:
    return _cup_rank_priority(_val(x, "cup_rank"))

def international_sort_key(x: Any):
    gpri = _gender_priority(_val(x, "gender"))
    apri = _age_priority(_val(x, "age_group"))
    bucket = _domestic_bucket(x)
    t = (_val(x, "type") or "").lower()
    tpri = _type_priority(t)
    metric = _league_metric(x) if t == "league" else (_cup_metric(x) if t == "cup" else 9999)
    name = _val(x, "name") or ""
    return (gpri, apri, bucket, tpri, metric, name)
