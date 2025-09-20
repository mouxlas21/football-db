from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Country
from .utils.helpers import _to_int
from .utils.resolvers import resolve_association_id
class CountriesImporter(BaseImporter):
    entity = "countries"

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        # consume name
        name = (raw.pop("name", None) or raw.pop("Name", None) or "").strip()
        if not name:
            return False, {}

        # fifa_code (normalize to upper, allow empty)
        fifa_code = (raw.pop("fifa_code", None) or raw.pop("FIFA", None) or raw.pop("code", None) or "")
        fifa_code = fifa_code.strip().upper() or None

        # Accept EITHER an integer confed_ass_id OR a code/name in the same column,
        # plus optional alternate headers for convenience.
        conf_token = (
            raw.pop("confed_ass_id", None)          # can be int ("2") or code ("UEFA") or name
            or raw.pop("confederation", None)       # e.g., "UEFA"
            or raw.pop("association", None)         # e.g., "FIFA"
        )
        confed_ass_id = resolve_association_id(conf_token, db)

        return True, {"name": name, "fifa_code": fifa_code, "confed_ass_id": confed_ass_id}

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        # name unique in schema
        stmt = insert(Country).values(**kwargs).on_conflict_do_nothing(index_elements=["name"])
        result = db.execute(stmt)
        return bool(getattr(result, "rowcount", 0))
