# backend/app/services/importers/stadiums.py
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Stadium

def _to_int(val):
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    return int(s) if s.isdigit() else None

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

class StadiumsImporter(BaseImporter):
    entity = "stadiums"

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        name = (raw.get("name") or "").strip()
        if not name:
            return False, {}
        city = (raw.get("city") or None) or None
        country_id = _to_int(raw.get("country_id"))
        capacity = _to_int(raw.get("capacity"))
        opened_year = _to_int(raw.get("opened_year"))
        lat = _to_float(raw.get("lat"))
        lng = _to_float(raw.get("lng"))
        return True, {
            "name": name,
            "city": city,
            "country_id": country_id,
            "capacity": capacity,
            "opened_year": opened_year,
            "lat": lat,
            "lng": lng,
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        # simple uniqueness heuristic: (name, country_id) if country present else (name, city)
        sel = select(Stadium).where(Stadium.name.ilike(kwargs["name"]))
        if kwargs.get("country_id"):
            sel = sel.where(Stadium.country_id == kwargs["country_id"])
        elif kwargs.get("city"):
            sel = sel.where(Stadium.city.ilike(kwargs["city"]))
        existing = db.execute(sel).scalar_one_or_none()
        if existing:
            # Optionally update some fields if provided
            changed = False
            for f in ("capacity","opened_year","lat","lng","city","country_id"):
                v = kwargs.get(f, None)
                if v is not None and getattr(existing, f) != v:
                    setattr(existing, f, v)
                    changed = True
            if changed:
                db.flush()
            return False

        stmt = insert(Stadium).values(**kwargs)
        res = db.execute(stmt)
        return bool(getattr(res, "rowcount", 0))
