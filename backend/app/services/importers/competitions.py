# backend/app/services/importers/competitions.py
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Competition

class CompetitionsImporter(BaseImporter):
    entity = "competitions"

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        # Expected headers: name, type, organizer, country_id, confederation
        name = (raw.get("name") or raw.get("Name") or "").strip()
        if not name:
            return False, {}
        type_val = (raw.get("type") or raw.get("Type") or "league").strip() or "league"
        organizer = (raw.get("organizer") or raw.get("Organizer") or None) or None
        confed = (raw.get("confederation") or raw.get("Confederation") or None) or None
        cid_raw = (raw.get("country_id") or raw.get("CountryID") or raw.get("countryId") or "").strip()
        country_id = int(cid_raw) if cid_raw.isdigit() else None

        return True, {
            "name": name,
            "type": type_val,
            "organizer": organizer,
            "country_id": country_id,
            "confederation": confed,
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        # competition.name is globally unique per schema
        stmt = insert(Competition).values(**kwargs).on_conflict_do_nothing(index_elements=["name"])
        result = db.execute(stmt)
        return bool(getattr(result, "rowcount", 0))
