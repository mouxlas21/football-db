# backend/app/services/importers/clubs.py
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Club, Country, Stadium

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

class ClubsImporter(BaseImporter):
    entity = "clubs"

    def _resolve_country_id(self, token, db: Session) -> int | None:
        # id → id; else FIFA code (upper) → id; else name (case-insensitive) → id
        if token is None:
            return None
        as_int = _to_int(token)
        if as_int is not None:
            return as_int
        val = str(token).strip()
        if not val:
            return None
        row = db.execute(select(Country).where(Country.fifa_code == val.upper())).scalar_one_or_none()
        if row:
            return row.country_id
        row = db.execute(select(Country).where(func.lower(Country.name) == func.lower(val))).scalar_one_or_none()
        return row.country_id if row else None

    def _resolve_stadium_id(self, token, db: Session, city_hint: str | None = None, country_id_hint: int | None = None) -> int | None:
        """
        Resolve stadium by:
        1) numeric id
        2) (name + city) exact (case-insensitive), if city_hint is given
        3) name + country (when country_id_hint is given)
        4) name only, but if multiple found → return None (ambiguous)
        """
        if token is None:
            return None

        as_int = _to_int(token)
        if as_int is not None:
            return as_int

        val = str(token).strip()
        if not val:
            return None

        # Prefer (name, city) if provided
        if city_hint:
            row = db.execute(
                select(Stadium).where(
                    and_(
                        func.lower(Stadium.name) == func.lower(val),
                        func.lower(Stadium.city) == func.lower(city_hint.strip())
                    )
                )
            ).scalar_one_or_none()
            if row:
                return row.stadium_id

        # Next: name within same country (if we know club country)
        if country_id_hint:
            rows = db.execute(
                select(Stadium).where(
                    and_(
                        func.lower(Stadium.name) == func.lower(val),
                        Stadium.country_id == country_id_hint
                    )
                )
            ).scalars().all()
            if len(rows) == 1:
                return rows[0].stadium_id
            # if 0 or >1, fall through to name-only

        # Finally: name only
        rows = db.execute(
            select(Stadium).where(func.lower(Stadium.name) == func.lower(val))
        ).scalars().all()
        if len(rows) == 1:
            return rows[0].stadium_id

        # ambiguous or none → don’t guess
        return None

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        name = (raw.pop("name", None) or raw.pop("Name", None) or "").strip()
        if not name:
            return False, {}

        short_name = (raw.pop("short_name", None) or raw.pop("ShortName", None) or None)
        if short_name:
            short_name = short_name.strip() or None

        founded = _to_int(raw.pop("founded", None) or raw.pop("Founded", None))

        # country can be id | FIFA code | country name
        country_token = raw.pop("country_id", None) or raw.pop("country", None)
        country_id = self._resolve_country_id(country_token, db)

        # allow 'stadium' alias, and optional city hint (use 'stadium_city' or 'city')
        stadium_token = raw.pop("stadium_id", None) or raw.pop("stadium", None)
        city_hint = (raw.pop("stadium_city", None) or raw.pop("city", None) or "").strip() or None

        colors = (raw.pop("colors", None) or raw.pop("Colors", None) or None)
        if colors:
            colors = colors.strip() or None

        stadium_id = self._resolve_stadium_id(stadium_token, db, city_hint=city_hint, country_id_hint=country_id)

        return True, {
            "name": name,
            "short_name": short_name,
            "founded": founded,
            "country_id": country_id,
            "stadium_id": stadium_id,
            "colors": colors,
        }


    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        stmt = (
            insert(Club)
            .values(**kwargs)
            .on_conflict_do_update(
                index_elements=["name"],    # schema unique
                set_={
                    "short_name": kwargs.get("short_name"),
                    "founded": kwargs.get("founded"),
                    "country_id": kwargs.get("country_id"),
                    "stadium_id": kwargs.get("stadium_id"),
                    "colors": kwargs.get("colors"),
                },
            )
        )
        res = db.execute(stmt)
        return bool(getattr(res, "rowcount", 0))
