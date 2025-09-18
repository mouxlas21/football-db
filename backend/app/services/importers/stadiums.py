# backend/app/services/importers/stadiums.py
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Stadium, Country

def _to_int(val):
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    try:
        return int(s)
    except Exception:
        return None

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

    def _resolve_country_id(self, token: str | None, db: Session) -> int | None:
        """
        Accepts in a single CSV column:
          - numeric id: "1" -> 1
          - FIFA code:  "GER", "ENG", "BRA" -> country_id
          - country name (case-insensitive exact): "Germany" -> country_id
        """
        if token is None:
            return None

        # numeric?
        as_int = _to_int(token)
        if as_int is not None:
            return as_int

        val = str(token).strip()
        if not val:
            return None

        # try FIFA code (stored uppercase)
        fifa = val.upper()
        row = db.execute(select(Country).where(Country.fifa_code == fifa)).scalar_one_or_none()
        if row:
            return row.country_id

        # fallback by name (case-insensitive exact)
        row = db.execute(
            select(Country).where(func.lower(Country.name) == func.lower(val))
        ).scalar_one_or_none()
        if row:
            return row.country_id

        return None

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        name = (raw.pop("name", None) or "").strip()
        if not name:
            return False, {}

        city = (raw.pop("city", None) or None)
        if city is not None:
            city = city.strip() or None

        # Accept country via multiple headers; prefer 'country_id' if present
        country_token = (
            raw.pop("country_id", None)
            or raw.pop("country", None)
            or raw.pop("country_name", None)
            or raw.pop("country_code", None)
            or raw.pop("fifa", None)
            or raw.pop("fifa_code", None)
        )
        country_id = self._resolve_country_id(country_token, db)

        capacity = _to_int(raw.pop("capacity", None))
        opened_year = _to_int(raw.pop("opened_year", None))
        lat = _to_float(raw.pop("lat", None))
        lng = _to_float(raw.pop("lng", None))

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
        """
        Heuristic:
          - If (name, country_id) matches, update mutable fields.
          - Else if (name, city) matches, update.
          - Else insert.
        """
        sel = select(Stadium).where(Stadium.name.ilike(kwargs["name"]))
        if kwargs.get("country_id"):
            sel = sel.where(Stadium.country_id == kwargs["country_id"])
        elif kwargs.get("city"):
            sel = sel.where(Stadium.city.ilike(kwargs["city"]))

        existing = db.execute(sel).scalar_one_or_none()
        if existing:
            changed = False
            for f in ("capacity", "opened_year", "lat", "lng", "city", "country_id"):
                v = kwargs.get(f, None)
                if v is not None and getattr(existing, f) != v:
                    setattr(existing, f, v)
                    changed = True
            if changed:
                db.flush()
            return False

        res = db.execute(insert(Stadium).values(**kwargs))
        return bool(getattr(res, "rowcount", 0))
