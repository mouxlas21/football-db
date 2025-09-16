from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Country, League

class LeaguesImporter(BaseImporter):
    entity = "leagues"

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        name = (raw.get("name") or raw.get("Name") or "").strip()
        if not name:
            return False, {}
        slug = (raw.get("slug") or raw.get("Slug") or None) or None

        tier_raw = (raw.get("tier") or raw.get("Tier") or "").strip()
        tier = int(tier_raw) if tier_raw.isdigit() else None

        cid_raw = (raw.get("country_id") or raw.get("CountryID") or raw.get("countryId") or "").strip()
        if not cid_raw.isdigit():
            return False, {}
        country_id = int(cid_raw)

        # Referential integrity check
        exists = db.execute(select(Country.country_id).where(Country.country_id == country_id)).scalar_one_or_none()
        if not exists:
            return False, {}

        return True, {"name": name, "slug": slug, "tier": tier, "country_id": country_id}

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        stmt = insert(League).values(**kwargs).on_conflict_do_nothing(index_elements=["name", "country_id"])
        result = db.execute(stmt)
        return bool(getattr(result, "rowcount", 0))
