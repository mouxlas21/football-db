# backend/app/services/importers/stages.py
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Stage, Season, Competition

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

class StagesImporter(BaseImporter):
    entity = "stages"

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        name = (raw.get("name") or "").strip()
        if not name:
            return False, {}
        season_id = _to_int(raw.get("season_id"))
        season_name = (raw.get("season_name") or "").strip()
        competition_name = (raw.get("competition_name") or "").strip()
        stage_order = _to_int(raw.get("stage_order")) or 1
        fmt = (raw.get("format") or "league").strip()

        if not season_id:
            # resolve by (competition_name, season_name)
            if not (competition_name and season_name):
                return False, {}
            comp = db.execute(select(Competition).where(Competition.name.ilike(competition_name))).scalar_one_or_none()
            if not comp:
                return False, {}
            season = db.execute(
                select(Season).where(Season.competition_id == comp.competition_id, Season.name == season_name)
            ).scalar_one_or_none()
            if not season:
                return False, {}
            season_id = season.season_id

        return True, {"season_id": season_id, "name": name, "stage_order": stage_order, "format": fmt}

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        existing = db.execute(
            select(Stage).where(Stage.season_id == kwargs["season_id"], Stage.name == kwargs["name"])
        ).scalar_one_or_none()
        if existing:
            changed = False
            for f in ("stage_order", "format"):
                v = kwargs.get(f)
                if v is not None and getattr(existing, f) != v:
                    setattr(existing, f, v)
                    changed = True
            if changed:
                db.flush()
            return False
        stmt = insert(Stage).values(**kwargs)
        res = db.execute(stmt)
        return bool(getattr(res, "rowcount", 0))
