from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Country

class CountriesImporter(BaseImporter):
    entity = "countries"

    def parse_row(self, raw: Dict[str, Any], db: Session):
        name = (raw.get("name") or raw.get("Name") or "").strip()
        if not name:
            return False, {}
        fifa_code = (raw.get("fifa_code") or raw.get("FIFA") or raw.get("code") or "").strip() or None
        if fifa_code:
            fifa_code = fifa_code.upper()
        return True, {"name": name, "fifa_code": fifa_code}

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        stmt = insert(Country).values(**kwargs).on_conflict_do_nothing(index_elements=["name"])  # schema unique
        result = db.execute(stmt)
        return bool(getattr(result, "rowcount", 0))
