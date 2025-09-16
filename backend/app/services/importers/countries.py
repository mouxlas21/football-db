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
        iso2 = (raw.get("iso2") or raw.get("ISO2") or raw.get("code") or "").strip() or None
        if iso2:
            iso2 = iso2.upper()
        return True, {"name": name, "iso2": iso2}

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        stmt = insert(Country).values(**kwargs).on_conflict_do_nothing(index_elements=["name"])  # schema unique
        result = db.execute(stmt)
        return bool(getattr(result, "rowcount", 0))
