# backend/app/services/importers/stages.py
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Stage, Season, Competition

ALLOWED_FORMATS = {"league","groups","knockout","qualification","playoffs"}

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

    def _resolve_season_id(self, season_token, comp_token, db: Session) -> int | None:
        """
        season_token can be:
          - numeric season_id
          - season name (e.g., '2024/25')
        comp_token can be:
          - competition name (preferred), or None if season_id was numeric
        """
        # numeric season id?
        sid = _to_int(season_token)
        if sid is not None:
            return sid

        # need competition context to resolve by (competition, season_name)
        season_name = (str(season_token or "").strip())
        if not (comp_token and season_name):
            return None

        comp_name = str(comp_token).strip()
        comp = db.execute(
            select(Competition).where(func.lower(Competition.name) == func.lower(comp_name))
        ).scalar_one_or_none()
        if not comp:
            return None

        season = db.execute(
            select(Season).where(
                Season.competition_id == comp.competition_id,
                Season.name == season_name
            )
        ).scalar_one_or_none()
        return season.season_id if season else None

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        # required stage name
        name = (raw.pop("name", None) or "").strip()
        if not name:
            return False, {}

        # accept both 'competition' and 'competition_name'
        comp_token = (raw.pop("competition_name", None) or raw.pop("competition", None) or "").strip() or None

        # accept season by id or by name:
        #  - 'season_id' may be a number OR a season name like '2024/25'
        #  - also accept explicit 'season_name'
        season_token = raw.pop("season_id", None)
        if season_token is None:
            season_token = raw.pop("season_name", None)

        season_id = self._resolve_season_id(season_token, comp_token, db)
        if not season_id:
            return False, {}

        # optional fields
        stage_order = _to_int(raw.pop("stage_order", None)) or 1
        fmt = (raw.pop("format", None) or "league").strip().lower()
        if fmt not in ALLOWED_FORMATS:
            fmt = "league"

        return True, {"season_id": season_id, "name": name, "stage_order": stage_order, "format": fmt}

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        existing = db.execute(
            select(Stage).where(
                Stage.season_id == kwargs["season_id"],
                Stage.name == kwargs["name"]
            )
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

        res = db.execute(insert(Stage).values(**kwargs))
        return bool(getattr(res, "rowcount", 0))
