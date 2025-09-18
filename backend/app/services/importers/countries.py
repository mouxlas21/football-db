# backend/app/services/importers/countries.py
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Country, Association

def _to_int(val):
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    try:
        return int(s)
    except Exception:
        return None

class CountriesImporter(BaseImporter):
    entity = "countries"

    def _resolve_ass_id(self, token: str | None, db: Session) -> int | None:
        """
        Accepts:
          - numeric id (e.g., "2") -> returns 2
          - code (e.g., "UEFA", "fifa") -> looks up Association.code (case-sensitive stored as upper)
          - name (e.g., "Union of European Football Associations") -> looks up by name (case-insensitive)
        """
        if token is None:
            return None

        # numeric?
        as_int = _to_int(token)
        if as_int is not None:
            return as_int

        val = str(token).strip()
        if not val:
            return None

        # by code (normalize to upper)
        code = val.upper()
        row = db.execute(select(Association).where(Association.code == code)).scalar_one_or_none()
        if row:
            return row.ass_id

        # by name (case-insensitive exact)
        row = db.execute(
            select(Association).where(func.lower(Association.name) == func.lower(val))
        ).scalar_one_or_none()
        if row:
            return row.ass_id

        return None

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
        confed_ass_id = self._resolve_ass_id(conf_token, db)

        return True, {"name": name, "fifa_code": fifa_code, "confed_ass_id": confed_ass_id}

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        # name unique in schema
        stmt = insert(Country).values(**kwargs).on_conflict_do_nothing(index_elements=["name"])
        result = db.execute(stmt)
        return bool(getattr(result, "rowcount", 0))
