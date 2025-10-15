from datetime import date, datetime, timezone

def _to_int(v):
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    try:
        return int(s)
    except Exception:
        return None
    
def _to_bool(v, *, default: bool = False) -> bool:
    """
    Convert v to bool. Accepts common truthy/falsey strings and ints.
    If v is None/empty/unknown, return `default`.
    """
    if v is None:
        return default
    s = str(v).strip().lower()
    if s == "":
        return default

    # truthy
    if s in ("1", "true", "t", "yes", "y", "on"):
        return True
    # falsey
    if s in ("0", "false", "f", "no", "n", "off"):
        return False

    # numbers (e.g., "2" → True, "0" → False)
    try:
        return bool(int(s))
    except Exception:
        return default

def _to_float(val):
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    try:
        return float(s)
    except Exception:
        return None
    
def _parse_date(v):
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except Exception:
        return None
    

def _parse_iso_date(value: str | None) -> date | None:
    if not value: return None
    v = str(value).strip()
    if not v: return None
    try: return date.fromisoformat(v)
    except Exception: return None

def _parse_dt(val: str | None) -> datetime | None:
    if not val:
        return None
    v = str(val).strip()
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None
    
def _decide_winner(home_team_id, away_team_id, home_final, away_final, went_pen, pen_home, pen_away):
    # Penalties decide the winner first, if present and non-draw
    if went_pen and pen_home is not None and pen_away is not None and pen_home != pen_away:
        return home_team_id if pen_home > pen_away else away_team_id
    # Otherwise use final score (after ET if present, else FT/explicit)
    if home_final is not None and away_final is not None and home_final != away_final:
        return home_team_id if home_final > away_final else away_team_id
    return None

def _to_int_list(val):
    if val is None:
        return None
    if isinstance(val, (list, tuple)):
        return [x for x in (_to_int(v) for v in val) if x is not None]
    s = str(val).strip()
    if not s:
        return None
    parts = [p.strip() for p in s.replace(';', ',').split(',')]
    out = []
    for p in parts:
        v = _to_int(p)
        if v is not None:
            out.append(v)
    return out or None

def _to_str_list(val):
    if val is None:
        return None
    if isinstance(val, (list, tuple)):
        out = [str(v).strip() for v in val if str(v).strip()]
        return out or None
    s = str(val)
    parts = [p.strip() for p in s.replace(';', ',').split(',')]
    out = [p for p in parts if p]
    return out or None