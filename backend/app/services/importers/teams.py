# backend/app/services/importers/teams.py
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Team, Club, Country

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

class TeamsImporter(BaseImporter):
    entity = "teams"

    def _resolve_country_id(self, token, db: Session) -> int | None:
        if token is None:
            return None
        as_int = _to_int(token)
        if as_int is not None:
            return as_int
        val = str(token).strip()
        if not val:
            return None
        # FIFA code
        row = db.execute(select(Country).where(Country.fifa_code == val.upper())).scalar_one_or_none()
        if row:
            return row.country_id
        # country name (case-insensitive)
        row = db.execute(select(Country).where(func.lower(Country.name) == func.lower(val))).scalar_one_or_none()
        return row.country_id if row else None

    def _resolve_club_id(self, token, db: Session) -> int | None:
        """
        Accept club_id as either:
          - numeric id
          - club name (case-insensitive exact) in the SAME 'club_id' column (matches your CSV)
        """
        if token is None:
            return None
        as_int = _to_int(token)
        if as_int is not None:
            return as_int
        # try by club name
        name = str(token).strip()
        if not name:
            return None
        c = db.execute(select(Club).where(func.lower(Club.name) == func.lower(name))).scalar_one_or_none()
        return c.club_id if c else None

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        name = (raw.pop("name", None) or "").strip()
        ttype = (raw.pop("type", None) or "club").strip().lower()
        if not name:
            return False, {}

        # Club side: club_id can be ID or *club name* (your current CSV)
        club_token = raw.pop("club_id", None)

        # National side: can be ID / FIFA / country name
        nat_token = raw.pop("national_country_id", None)

        # Optional descriptors
        gender = (raw.pop("gender", None) or "").strip() or None
        age_group = (raw.pop("age_group", None) or "").strip() or None
        squad_level = (raw.pop("squad_level", None) or "").strip() or None

        club_id = self._resolve_club_id(club_token, db) if ttype == "club" else None
        national_country_id = self._resolve_country_id(nat_token, db) if ttype == "national" else None

        # Enforce XOR to match DB CHECK
        if ttype == "club":
            if not club_id or national_country_id:
                return False, {}
        elif ttype == "national":
            if not national_country_id or club_id:
                return False, {}
        else:
            return False, {}

        return True, {
            "name": name,
            "type": ttype,
            "club_id": club_id,
            "national_country_id": national_country_id,
            "gender": gender,
            "age_group": age_group,
            "squad_level": squad_level,
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        # Prevent duplicates by (name, type)
        existing = db.execute(
            select(Team).where(and_(func.lower(Team.name) == func.lower(kwargs["name"]), Team.type == kwargs["type"]))
        ).scalar_one_or_none()

        if existing:
            changed = False
            for f in ("club_id", "national_country_id", "gender", "age_group", "squad_level"):
                v = kwargs.get(f)
                if v is not None and getattr(existing, f) != v:
                    setattr(existing, f, v)
                    changed = True
            if changed:
                db.flush()
            return False

        res = db.execute(insert(Team).values(**kwargs))
        return bool(getattr(res, "rowcount", 0))