# backend/app/services/importers/teams.py
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Team, Club

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

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        name = (raw.get("name") or "").strip()
        ttype = (raw.get("type") or "club").strip()
        if not name:
            return False, {}

        team_id = _to_int(raw.get("team_id"))
        club_id = _to_int(raw.get("club_id"))
        club_name = (raw.get("club_name") or "").strip()
        national_country_id = _to_int(raw.get("national_country_id"))

        # Resolve club by name if not given id
        if ttype == "club" and not club_id and club_name:
            c = db.execute(select(Club).where(Club.name.ilike(club_name))).scalar_one_or_none()
            club_id = c.club_id if c else None

        return True, {
            "team_id": team_id,  # may be None; we'll strip it later before insert
            "name": name,
            "type": ttype,
            "club_id": club_id,
            "national_country_id": national_country_id,
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        # If caller provided an explicit team_id, we must use OVERRIDING SYSTEM VALUE
        tid = kwargs.get("team_id")

        if tid:
            existing = db.execute(select(Team).where(Team.team_id == tid)).scalar_one_or_none()
            if existing:
                changed = False
                for f in ("name", "type", "club_id", "national_country_id"):
                    v = kwargs.get(f)
                    if v is not None and getattr(existing, f) != v:
                        setattr(existing, f, v)
                        changed = True
                if changed:
                    db.flush()
                return False

            stmt = (
                insert(Team)
                .values(**kwargs)
                .prefix_with("OVERRIDING SYSTEM VALUE")
                .on_conflict_do_nothing(index_elements=["team_id"])
            )
            res = db.execute(stmt)
            return bool(getattr(res, "rowcount", 0))

        # No team_id: let Postgres generate it. IMPORTANT: drop team_id key entirely
        insert_kwargs = {k: v for k, v in kwargs.items() if k != "team_id"}

        # Basic de-duplication: (name, type)
        existing = db.execute(
            select(Team).where(Team.name.ilike(insert_kwargs["name"]), Team.type == insert_kwargs["type"])
        ).scalar_one_or_none()
        if existing:
            # Optionally patch club/national_country
            changed = False
            for f in ("club_id", "national_country_id"):
                v = insert_kwargs.get(f)
                if v is not None and getattr(existing, f) != v:
                    setattr(existing, f, v)
                    changed = True
            if changed:
                db.flush()
            return False

        stmt = insert(Team).values(**insert_kwargs)  # no team_id column here
        res = db.execute(stmt)
        return bool(getattr(res, "rowcount", 0))
