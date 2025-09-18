# backend/app/services/importers/officials.py
from typing import Dict, Any, Tuple
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Person, Official, Association

def _parse_iso_date(v: str | None) -> date | None:
    if not v: return None
    s = str(v).strip()
    if not s: return None
    try: return date.fromisoformat(s)
    except Exception: return None

def _to_int(v):
    if v is None: return None
    s = str(v).strip()
    if s == "": return None
    try: return int(s)
    except Exception: return None

class OfficialsImporter(BaseImporter):
    entity = "officials"

    def _resolve_association(self, token, db: Session) -> int | None:
        if token is None: return None
        as_int = _to_int(token)
        if as_int is not None: return as_int
        val = str(token).strip()
        if not val: return None
        row = db.execute(select(Association).where(Association.code == val.upper())).scalar_one_or_none()
        if row: return row.ass_id
        row = db.execute(select(Association).where(func.lower(Association.name) == func.lower(val))).scalar_one_or_none()
        return row.ass_id if row else None

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        full_name = (raw.get("full_name") or "").strip()
        if not full_name: return False, {}

        known_as = (raw.get("known_as") or "").strip() or None
        birth_date = _parse_iso_date(raw.get("birth_date") or raw.get("dob"))
        association_id = self._resolve_association(raw.get("association") or raw.get("association_id") or raw.get("federation"), db)
        roles = (raw.get("roles") or "").strip() or None

        active_raw = str(raw.get("active") or raw.get("official_active") or "").strip().lower()
        official_active = True if active_raw in ("1","true","t","yes","y") else False if active_raw in ("0","false","f","no","n") else True

        return True, {
            "full_name": full_name,
            "known_as": known_as,
            "birth_date": birth_date,
            "association_id": association_id,
            "roles": roles,
            "official_active": official_active,  # <-- matches model
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
            insert(Official)
            .values(
                person_id=person.person_id,
                association_id=kwargs.get("association_id"),
                roles=kwargs.get("roles"),
                official_active=kwargs.get("official_active"),
            )
            .on_conflict_do_update(
                index_elements=["person_id"],
                set_={
                    "association_id": kwargs.get("association_id"),
                    "roles": kwargs.get("roles"),
                    "official_active": kwargs.get("official_active"),
                },
            )
        )
        res = db.execute(stmt)
        return bool(getattr(res, "rowcount", 0))
