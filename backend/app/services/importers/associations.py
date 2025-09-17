from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Association

def _to_int(val):
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    return int(s) if s.isdigit() else None

class AssociationsImporter(BaseImporter):
    entity = "associations"

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        code = (raw.get("code") or "").strip().upper()
        name = (raw.get("name") or "").strip()
        level = (raw.get("level") or "").strip().lower()  # 'federation'|'confederation'|'association'|'league_body'

        if not code or not name or level not in {"federation","confederation","association","league_body"}:
            return False, {}

        parent_org_id = _to_int(raw.pop("parent_org_id", None))

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
