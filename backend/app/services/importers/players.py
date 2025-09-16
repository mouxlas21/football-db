# backend/app/services/importers/players.py
from typing import Dict, Any, Tuple
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Person, Player

def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    v = value.strip()
    if not v:
        return None
    try:
        # Expecting YYYY-MM-DD
        return date.fromisoformat(v)
    except Exception:
        return None

class PlayersImporter(BaseImporter):
    entity = "players"

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        # Expected headers:
        # full_name, known_as, dob (YYYY-MM-DD), country_id, height_cm, weight_kg, foot, primary_position
        full_name = (raw.get("full_name") or raw.get("FullName") or "").strip()
        if not full_name:
            return False, {}
        known_as = (raw.get("known_as") or raw.get("KnownAs") or None) or None
        dob_str = (raw.get("dob") or raw.get("DOB") or None)
        dob = _parse_iso_date(dob_str)

        country_id_raw = (raw.get("country_id") or "").strip()
        country_id = int(country_id_raw) if str(country_id_raw).isdigit() else None

        height_raw = (raw.get("height_cm") or "").strip()
        height_cm = int(height_raw) if str(height_raw).isdigit() else None

        weight_raw = (raw.get("weight_kg") or "").strip()
        weight_kg = int(weight_raw) if str(weight_raw).isdigit() else None

        foot = (raw.get("foot") or None) or None
        primary_position = (raw.get("primary_position") or None) or None

        return True, {
            "full_name": full_name,
            "known_as": known_as,
            "dob": dob,  # Python date (or None)
            "country_id": country_id,
            "height_cm": height_cm,
            "weight_kg": weight_kg,
            "foot": foot,
            "primary_position": primary_position,
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        # Heuristic: try to find existing person by (full_name, dob)
        sel = select(Person).where(Person.full_name.ilike(kwargs["full_name"]))
        if kwargs.get("dob") is not None:
            sel = sel.where(Person.dob == kwargs["dob"])  # both are date
        person = db.execute(sel).scalar_one_or_none()

        if not person:
            person = Person(
                full_name=kwargs["full_name"],
                known_as=kwargs.get("known_as"),
                dob=kwargs.get("dob"),  # already a date
                country_id=kwargs.get("country_id"),
                height_cm=kwargs.get("height_cm"),
                weight_kg=kwargs.get("weight_kg"),
            )
            db.add(person)
            db.flush()

        # Ensure player row exists for this person
        stmt = insert(Player).values(
            player_id=person.person_id,
            foot=kwargs.get("foot"),
            primary_position=kwargs.get("primary_position"),
        ).on_conflict_do_nothing(index_elements=["player_id"])
        result = db.execute(stmt)
        return bool(getattr(result, "rowcount", 0))
