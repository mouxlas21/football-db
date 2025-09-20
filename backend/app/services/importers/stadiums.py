from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Stadium
from .utils.helpers import _to_int, _to_float
from .utils.resolvers import resolve_country_id

class StadiumsImporter(BaseImporter):
    entity = "stadiums"

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
        country_id = resolve_country_id(country_token, db)

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
