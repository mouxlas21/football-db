from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Club
from .utils.helpers import _to_int
from .utils.resolvers import resolve_country_id, resolve_stadium_id

class ClubsImporter(BaseImporter):
    entity = "clubs"

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
        country_id = resolve_country_id(country_token, db)

        # allow 'stadium' alias, and optional city hint (use 'stadium_city' or 'city')
        stadium_token = raw.pop("stadium_id", None) or raw.pop("stadium", None)
        city_hint = (raw.pop("stadium_city", None) or raw.pop("city", None) or "").strip() or None

        colors = (raw.pop("colors", None) or raw.pop("Colors", None) or None)
        if colors:
            colors = colors.strip() or None

        stadium_id = resolve_stadium_id(stadium_token, db, city_hint=city_hint, country_id_hint=country_id)

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
