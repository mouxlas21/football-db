from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Competition, Association

class CompetitionsImporter(BaseImporter):
    entity = "competitions"

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        name = (raw.get("name") or raw.get("Name") or "").strip()
        if not name:
            return False, {}
        type_val = (raw.get("type") or raw.get("Type") or "league").strip() or "league"
        cid_raw = (raw.get("country_id") or raw.get("CountryID") or raw.get("countryId") or "").strip()
        country_id = int(cid_raw) if cid_raw.isdigit() else None
        org_code = (raw.pop("organizer_code", None) or raw.pop("organizer", None) or "").strip().upper() or None
        confed_ass_id = None
        if org_code:
            row = db.execute(select(Association).where(Association.code == org_code)).scalar_one_or_none()
            confed_ass_id = row.ass_id if row else None

        return True, {
            "name": name,
            "type": type_val,
            "country_id": country_id,
            "confed_ass_id": confed_ass_id,
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        # competition.name is globally unique per schema
        stmt = insert(Competition).values(**kwargs).on_conflict_do_nothing(index_elements=["name"])
        result = db.execute(stmt)
        return bool(getattr(result, "rowcount", 0))
