from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Association
from .utils.helpers import _to_int

class AssociationsImporter(BaseImporter):
    entity = "associations"

    def _resolve_parent_id(self, token: str | None, db: Session) -> int | None:
        """
        Accepts:
          - numeric id (e.g., "1" or 1) -> returns that id
          - code (e.g., "FIFA", "uefa") -> looks up Association.code (case-insensitive)
          - name (e.g., "Fédération Internationale de Football Association") -> looks up by name (case-insensitive)
        """
        if token is None:
            return None

        # try integer first
        as_int = _to_int(token)
        if as_int is not None:
            return as_int

        val = str(token).strip()
        if not val:
            return None

        # Try by code (normalized uppercase exact)
        code = val.upper()
        row = db.execute(
            select(Association).where(Association.code == code)
        ).scalar_one_or_none()
        if row:
            return row.ass_id

        # Fallback: try by name (case-insensitive exact)
        row = db.execute(
            select(Association).where(func.lower(Association.name) == func.lower(val))
        ).scalar_one_or_none()
        if row:
            return row.ass_id

        return None

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        code = (raw.pop("code", None) or "").strip().upper()
        name = (raw.pop("name", None) or "").strip()
        level = (raw.pop("level", None) or "").strip().lower()  # 'federation'|'confederation'|'association'|'league_body'

        if not code or not name or level not in {"federation", "confederation", "association", "league_body"}:
            return False, {}

        # Accept parent_org_id as:
        #  - numeric id (e.g., 1)
        #  - association code (e.g., 'FIFA', 'UEFA')
        #  - association name (case-insensitive full match)
        parent_token = raw.pop("parent_org_id", None)
        parent_org_id = self._resolve_parent_id(parent_token, db)

        return True, {"code": code, "name": name, "level": level, "parent_org_id": parent_org_id}

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        # code is unique
        stmt = insert(Association).values(**kwargs).on_conflict_do_update(
            index_elements=["code"],
            set_={
                "name": kwargs["name"],
                "level": kwargs["level"],
                "parent_org_id": kwargs["parent_org_id"],
            },
        )
        res = db.execute(stmt)
        return bool(getattr(res, "rowcount", 0))
