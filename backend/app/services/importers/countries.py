from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
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
        fifa_code = (
            raw.pop("fifa_code", None)
            or raw.pop("FIFA", None)
            or raw.pop("code", None)
            or ""
        )
        fifa_code = fifa_code.strip().upper() or None

        # Accept EITHER an integer confed_ass_id OR a code/name in the same column,
        # plus optional alternate headers for convenience.
        conf_token = (
            raw.pop("confed_ass_id", None)
            or raw.pop("confederation", None)
            or raw.pop("association", None)
        )
        confed_ass_id = resolve_association_id(conf_token, db)

        # flag filename
        flag_filename = (raw.pop("flag_filename", None) or raw.pop("flag", None) or None)
        if flag_filename:
            flag_filename = flag_filename.strip() or None

        # NEW: c_status (active/historical)
        c_status = (
            raw.pop("c_status", None)
            or raw.pop("status", None)
            or "active"
        )
        c_status = c_status.strip().lower()
        if c_status not in ("active", "historical"):
            c_status = "active"

        return True, {
            "name": name,
            "fifa_code": fifa_code,
            "confed_ass_id": confed_ass_id,
            "flag_filename": flag_filename,
            "c_status": c_status,   # <-- pass to model
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        stmt = (
            insert(Country)
            .values(**kwargs)
            .on_conflict_do_update(
                index_elements=["name"],
                set_={"updated_at": func.now()},
            )
        )
        res = db.execute(stmt)
        return bool(getattr(res, "rowcount", 0))
