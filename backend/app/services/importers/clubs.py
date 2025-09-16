from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Club, Country, Stadium

class ClubsImporter(BaseImporter):
    entity = "clubs"

    def parse_row(self, raw: Dict[str, Any], db: Session):
        name = (raw.get("name") or raw.get("Name") or "").strip()
        if not name:
            return False, {}

        short_name = (raw.get("short_name") or raw.get("ShortName") or None) or None
        f_raw = (raw.get("founded") or raw.get("Founded") or "").strip()
        founded = int(f_raw) if f_raw.isdigit() else None

        cid_raw = (raw.get("country_id") or raw.get("CountryID") or raw.get("countryId") or "").strip()
        country_id = int(cid_raw) if cid_raw.isdigit() else None
        if country_id:
            ok = db.execute(select(Country.country_id).where(Country.country_id == country_id)).scalar_one_or_none()
            if not ok:
                return False, {}

        sid_raw = (raw.get("stadium_id") or raw.get("StadiumID") or raw.get("stadiumId") or "").strip()
        stadium_id = int(sid_raw) if sid_raw.isdigit() else None
        if stadium_id:
            ok = db.execute(select(Stadium.stadium_id).where(Stadium.stadium_id == stadium_id)).scalar_one_or_none()
            if not ok:
                return False, {}

        colors = (raw.get("colors") or raw.get("Colors") or None) or None

        return True, {"name": name, "short_name": short_name, "founded": founded,
                      "country_id": country_id, "stadium_id": stadium_id, "colors": colors}

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        stmt = insert(Club).values(**kwargs).on_conflict_do_nothing(index_elements=["name"])  # schema unique
        result = db.execute(stmt)
        return bool(getattr(result, "rowcount", 0))
