# backend/app/services/importers/coaches.py
from typing import Dict, Any, Tuple
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Person, Coach

def _parse_iso_date(v: str | None) -> date | None:
    if not v: return None
    s = str(v).strip()
    if not s: return None
    try: return date.fromisoformat(s)
    except Exception: return None

class CoachesImporter(BaseImporter):
    entity = "coaches"

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        full_name = (raw.get("full_name") or "").strip()
        if not full_name: return False, {}

        known_as = (raw.get("known_as") or "").strip() or None
        birth_date = _parse_iso_date(raw.get("birth_date") or raw.get("dob"))
        role_default = (raw.get("role_default") or "").strip() or None

        active_raw = str(raw.get("active") or raw.get("coach_active") or "").strip().lower()
        coach_active = True if active_raw in ("1","true","t","yes","y") else False if active_raw in ("0","false","f","no","n") else True

        return True, {
            "full_name": full_name,
            "known_as": known_as,
            "birth_date": birth_date,
            "role_default": role_default,
            "coach_active": coach_active,   # <-- matches model
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        sel = select(Person).where(func.lower(Person.full_name) == func.lower(kwargs["full_name"]))
        if kwargs.get("birth_date") is not None:
            sel = sel.where(Person.birth_date == kwargs["birth_date"])
        person = db.execute(sel).scalar_one_or_none()

        if not person:
            person = Person(
                full_name=kwargs["full_name"],
                known_as=kwargs.get("known_as"),
                birth_date=kwargs.get("birth_date"),
            )
            db.add(person); db.flush()
        else:
            if kwargs.get("known_as") and person.known_as != kwargs["known_as"]:
                person.known_as = kwargs["known_as"]; db.flush()

        stmt = (
            insert(Coach)
            .values(person_id=person.person_id, role_default=kwargs.get("role_default"), coach_active=kwargs.get("coach_active"))
            .on_conflict_do_update(
                index_elements=["person_id"],
                set_={"role_default": kwargs.get("role_default"), "coach_active": kwargs.get("coach_active")},
            )
        )
        res = db.execute(stmt)
        return bool(getattr(res, "rowcount", 0))
