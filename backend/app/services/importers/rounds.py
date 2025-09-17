# backend/app/services/importers/rounds.py
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Round, Stage, Season

def _to_int(v):
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    try:
        return int(s)
    except Exception:
        return None

def _to_bool(v):
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ("1","true","t","yes","y")

class RoundsImporter(BaseImporter):
    entity = "rounds"

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        name = (raw.get("name") or "").strip()
        if not name:
            return False, {}
        stage_id = _to_int(raw.get("stage_id"))
        stage_name = (raw.get("stage_name") or "").strip()
        season_name = (raw.get("season_name") or "").strip()
        round_order = _to_int(raw.get("round_order")) or 1
        two_legs = _to_bool(raw.get("two_legs"))

        if not stage_id:
            if not (season_name and stage_name):
                return False, {}
            # find stage by (season_name) -> latest season with that name
            st = db.execute(
                select(Stage).join(Season, Stage.season_id == Season.season_id).where(
                    Season.name == season_name, Stage.name == stage_name
                )
            ).scalar_one_or_none()
            if not st:
                return False, {}
            stage_id = st.stage_id

        return True, {"stage_id": stage_id, "name": name, "round_order": round_order, "two_legs": two_legs}

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        existing = db.execute(
            select(Round).where(Round.stage_id == kwargs["stage_id"], Round.name == kwargs["name"])
        ).scalar_one_or_none()
        if existing:
            changed = False
            for f in ("round_order","two_legs"):
                v = kwargs.get(f)
                if v is not None and getattr(existing, f) != v:
                    setattr(existing, f, v)
                    changed = True
            if changed:
                db.flush()
            return False
        stmt = insert(Round).values(**kwargs)
        res = db.execute(stmt)
        return bool(getattr(res, "rowcount", 0))
