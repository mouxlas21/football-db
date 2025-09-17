# backend/app/services/importers/seasons.py
from typing import Dict, Any, Tuple
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Season, Competition

def _parse_date(v):
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except Exception:
        return None

class SeasonsImporter(BaseImporter):
    entity = "seasons"

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        name = (raw.get("name") or "").strip()
        comp_id = raw.get("competition_id")
        comp_name = (raw.get("competition_name") or "").strip()

        if not name or (not comp_id and not comp_name):
            return False, {}

        # resolve competition_id by name if needed
        if not comp_id and comp_name:
            c = db.execute(select(Competition).where(Competition.name.ilike(comp_name))).scalar_one_or_none()
            comp_id = c.competition_id if c else None
        try:
            comp_id = int(comp_id) if comp_id else None
        except Exception:
            comp_id = None
        if not comp_id:
            return False, {}

        start_date = _parse_date(raw.get("start_date"))
        end_date = _parse_date(raw.get("end_date"))

        return True, {"competition_id": comp_id, "name": name, "start_date": start_date, "end_date": end_date}

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        # unique (competition_id, name)
        existing = db.execute(
            select(Season).where(Season.competition_id == kwargs["competition_id"], Season.name == kwargs["name"])
        ).scalar_one_or_none()
        if existing:
            changed = False
            for f in ("start_date", "end_date"):
                v = kwargs.get(f)
                if v is not None and getattr(existing, f) != v:
                    setattr(existing, f, v)
                    changed = True
            if changed:
                db.flush()
            return False

        stmt = insert(Season).values(**kwargs)
        res = db.execute(stmt)
        return bool(getattr(res, "rowcount", 0))
