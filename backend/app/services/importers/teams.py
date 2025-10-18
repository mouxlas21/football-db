from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Team, Club, Country
from .utils.helpers import _to_int
from .utils.resolvers import resolve_club_id,resolve_country_id

class TeamsImporter(BaseImporter):
    entity = "teams"

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        name = (raw.pop("name", None) or "").strip()
        ttype = (raw.pop("type", None) or "club").strip().lower()

        # Optional descriptors
        gender = (raw.pop("gender", None) or "").strip() or None
        age_group = (raw.pop("age_group", None) or "").strip() or None
        squad_level = (raw.pop("squad_level", None) or "").strip() or None

        # Club side: club_id can be ID or *club name*
        club_token = raw.pop("club_id", None)
        # National side: can be ID / FIFA / country name
        nat_token = raw.pop("national_country_id", None)

        club_id = resolve_club_id(club_token, db) if ttype == "club" else None
        national_country_id = resolve_country_id(nat_token, db) if ttype == "national" else None

        # Enforce XOR to match DB CHECK
        if ttype == "club":
            if not club_id or national_country_id:
                return False, {}
        elif ttype == "national":
            if not national_country_id or club_id:
                return False, {}
        else:
            return False, {}

        # Keep your current rule: name required
        if not name:
            if ttype == "club" and club_id:
                row = db.execute(select(Club).where(Club.club_id == club_id)).scalar_one_or_none()
                name = row.name if row else None
            elif ttype == "national" and national_country_id:
                row = db.execute(select(Country).where(Country.country_id == national_country_id)).scalar_one_or_none()
                name = row.name if row else None
            if not name:
                return False, {}
            
        # logo filename (single; small/big handled by template helper later)
        logo_filename = (raw.pop("logo_filename", None) or raw.pop("logo", None) or None)
        if logo_filename:
            logo_filename = logo_filename.strip() or None

        return True, {
            "name": name,
            "type": ttype,
            "club_id": club_id,
            "national_country_id": national_country_id,
            "logo_filename": logo_filename,
            "gender": gender,
            "age_group": age_group,
            "squad_level": squad_level,
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        """
        Upsert by (lower(name), type). If found, update selected fields in-place.
        Returns True if an INSERT happened, False if we only UPDATED/NO-OP.
        """
        # Find existing by (name, type) as in your current logic
        existing = db.execute(
            select(Team).where(
                and_(
                    func.lower(Team.name) == func.lower(kwargs["name"]),
                    Team.type == kwargs["type"],
                )
            )
        ).scalar_one_or_none()

        if existing:
            changed = False
            # now also track logo_filename in updates
            for f in ("club_id", "national_country_id", "gender", "age_group", "squad_level", "logo_filename"):
                v = kwargs.get(f)
                if v is not None and getattr(existing, f) != v:
                    setattr(existing, f, v)
                    changed = True
            if changed:
                existing.updated_at = func.now()
                db.flush()
            # return False to indicate we didn't INSERT (same as your original pattern)
            return False

        # No existing row -> INSERT
        res = db.execute(insert(Team).values(**kwargs))
        return bool(getattr(res, "rowcount", 0))
