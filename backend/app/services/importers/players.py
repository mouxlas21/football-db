from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Person, Player, Country
from .utils.helpers import _to_int, _parse_iso_date

ALLOWED_POS = {"GK", "DF", "MF", "FW"}

class PlayersImporter(BaseImporter):
    entity = "players"

    def _resolve_country_id(self, token, db: Session) -> int | None:
        if token is None: return None
        as_int = _to_int(token)
        if as_int is not None: return as_int
        val = str(token).strip()
        if not val: return None
        row = db.execute(select(Country).where(Country.fifa_code == val.upper())).scalar_one_or_none()
        if row: return row.country_id
        row = db.execute(select(Country).where(func.lower(Country.name) == func.lower(val))).scalar_one_or_none()
        return row.country_id if row else None

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        """
        CSV headers accepted:
          full_name, known_as, birth_date(=dob), country_id(=country),
          height_cm, weight_kg, position, active
        """
        full_name = (raw.get("full_name") or "").strip()
        if not full_name: return False, {}

        known_as = (raw.get("known_as") or "").strip() or None
        birth_date = _parse_iso_date(raw.get("birth_date") or raw.get("dob"))
        country_id = self._resolve_country_id(raw.get("country_id") or raw.get("country"), db)
        height_cm = _to_int(raw.get("height_cm"))
        weight_kg = _to_int(raw.get("weight_kg"))

        pos = (raw.get("position") or "").strip().upper() or None
        if pos and pos not in ALLOWED_POS:
            pos = None

        active_raw = str(raw.get("active") or "").strip().lower()
        player_active = True if active_raw in ("1","true","t","yes","y") else False if active_raw in ("0","false","f","no","n") else True

        return True, {
            "full_name": full_name,
            "known_as": known_as,
            "birth_date": birth_date,
            "country_id": country_id,
            "height_cm": height_cm,
            "weight_kg": weight_kg,
            "player_position": pos,     # <-- matches model
            "player_active": player_active,  # <-- matches model
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        # Person upsert by (full_name[, birth_date])
        sel = select(Person).where(func.lower(Person.full_name) == func.lower(kwargs["full_name"]))
        if kwargs.get("birth_date") is not None:
            sel = sel.where(Person.birth_date == kwargs["birth_date"])
        person = db.execute(sel).scalar_one_or_none()

        if not person:
            person = Person(
                full_name=kwargs["full_name"],
                known_as=kwargs.get("known_as"),
                birth_date=kwargs.get("birth_date"),
                country_id=kwargs.get("country_id"),
                height_cm=kwargs.get("height_cm"),
                weight_kg=kwargs.get("weight_kg"),
            )
            db.add(person)
            db.flush()
        else:
            changed = False
            for f in ("known_as","country_id","height_cm","weight_kg"):
                v = kwargs.get(f)
                if v is not None and getattr(person, f) != v:
                    setattr(person, f, v); changed = True
            if changed: db.flush()

        # Player upsert keyed by person_id
        stmt = (
            insert(Player)
            .values(
                person_id=person.person_id,
                player_position=kwargs.get("player_position"),
                player_active=kwargs.get("player_active"),
            )
            .on_conflict_do_update(
                index_elements=["person_id"],
                set_={
                    "player_position": kwargs.get("player_position"),
                    "player_active": kwargs.get("player_active"),
                },
            )
        )
        res = db.execute(stmt)
        return bool(getattr(res, "rowcount", 0))
