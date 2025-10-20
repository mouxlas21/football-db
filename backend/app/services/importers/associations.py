from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func, delete
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Association, association_parent
from .utils.helpers import _to_int

import json, re

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
    
    def _split_tokens(self, val) -> list[str]:
        if not val:
            return []
        s = str(val).strip()
        # JSON array first
        if s.startswith("[") and s.endswith("]"):
            try:
                data = json.loads(s)
                if isinstance(data, list):
                    return [str(x) for x in data]
            except Exception:
                pass
        # Fallback: comma / semicolon
        return [t.strip() for t in re.split(r"[;,]", s) if t.strip()]


    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        code = (raw.pop("code", None) or "").strip().upper()
        name = (raw.pop("name", None) or "").strip()
        founded_year = _to_int(raw.pop("founded_year", None))
        level = (raw.pop("level", None) or "").strip().lower()
        level = level.replace("-", "_")

        allowed = {"federation","confederation","sub_confederation","association","league_body"}
        if not code or not name or level not in allowed:
            return False, {}

        logo_filename = (raw.pop("logo_filename", None) or raw.pop("logo", None) or None)
        if logo_filename:
            logo_filename = logo_filename.strip() or None

        # Accept multiple parents via 'parents' | 'parent_org_id' | 'parent'
        parents_raw = raw.pop("parents", None) or raw.pop("parent_org_id", None) or raw.pop("parent", None)
        parent_tokens = self._split_tokens(parents_raw)
        parent_ids = [pid for tok in parent_tokens if (pid := self._resolve_parent_id(tok, db))]

        return True, {
            "code": code,
            "name": name,
            "founded_year": founded_year,
            "level": level,
            "logo_filename": logo_filename,
            "_parent_ids": parent_ids,   # handled in upsert
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        parent_ids = kwargs.pop("_parent_ids", [])

        # Upsert association by unique code
        stmt = insert(Association).values(**kwargs).on_conflict_do_update(
            index_elements=["code"],
            set_={
                "name": kwargs["name"],
                "founded_year": kwargs["founded_year"],
                "level": kwargs["level"],
                "logo_filename": kwargs.get("logo_filename"),
                "updated_at": func.now(),
            },
        )
        db.execute(stmt)

        # Fetch ass_id after upsert
        ass_id = db.execute(select(Association.ass_id).where(Association.code == kwargs["code"])).scalar_one()

        # Replace parent links atomically: delete then insert unique set
        db.execute(delete(association_parent).where(association_parent.c.ass_id == ass_id))
        if parent_ids:
            rows = [{"ass_id": ass_id, "parent_ass_id": pid} for pid in sorted(set(parent_ids))]
            db.execute(association_parent.insert(), rows)

        return True

