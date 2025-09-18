# backend/app/services/importers/seasons.py
from typing import Dict, Any, Tuple
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select, func
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

class SeasonsImporter(BaseImporter):
    entity = "seasons"

    def _resolve_competition_id(self, token: str | None, db: Session) -> int | None:
        """
        Accepts:
          - numeric id (e.g., "1")
          - competition name (case-insensitive exact): "Bundesliga", "FA Cup"
        """
        if token is None:
            return None

        # Try as integer id
        as_int = _to_int(token)
        if as_int is not None:
            return as_int

        # Else try by name (case-insensitive exact)
        name = str(token).strip()
        if not name:
            return None
        row = db.execute(
            select(Competition).where(func.lower(Competition.name) == func.lower(name))
        ).scalar_one_or_none()
        return row.competition_id if row else None

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        # name (e.g., "2024/25")
        name = (raw.pop("name", None) or "").strip()
        if not name:
            return False, {}

        # Accept competition from multiple headers:
        # - 'competition_id' (can be id OR name)
        # - or explicit 'competition_name' / 'competition'
        comp_token = (
            raw.pop("competition_id", None)
            or raw.pop("competition_name", None)
            or raw.pop("competition", None)
        )
        competition_id = self._resolve_competition_id(comp_token, db)
        if not competition_id:
            return False, {}

        start_date = _parse_date(raw.pop("start_date", None))
        end_date = _parse_date(raw.pop("end_date", None))

        return True, {
            "competition_id": competition_id,
            "name": name,
            "start_date": start_date,
            "end_date": end_date,
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        # unique (competition_id, name)
        existing = db.execute(
            select(Season).where(
                Season.competition_id == kwargs["competition_id"],
                Season.name == kwargs["name"],
            )
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

        res = db.execute(insert(Season).values(**kwargs))
        return bool(getattr(res, "rowcount", 0))
