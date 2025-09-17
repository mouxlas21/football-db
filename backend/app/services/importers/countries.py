from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Country, Association

def _to_int(val):
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    return int(s) if s.isdigit() else None

class CountriesImporter(BaseImporter):
    entity = "countries"

    def parse_row(self, raw: Dict[str, Any], db: Session):
        name = (raw.get("name") or raw.get("Name") or "").strip()
        if not name:
            return False, {}
        fifa_code = (raw.get("fifa_code") or raw.get("FIFA") or raw.get("code") or "").strip() or None
        if fifa_code:
            fifa_code = fifa_code.upper()
        confed_ass_id = _to_int(raw.pop("confed_ass_id", None))
        return True, {"name": name, "fifa_code": fifa_code, "confed_ass_id": confed_ass_id}

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        stmt = insert(Country).values(**kwargs).on_conflict_do_nothing(index_elements=["name"])  # schema unique
        result = db.execute(stmt)
        return bool(getattr(result, "rowcount", 0))
