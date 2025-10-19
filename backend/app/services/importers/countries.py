from typing import Dict, Any, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import func, select, delete, Table
from sqlalchemy.dialects.postgresql import insert

from .base import BaseImporter
from app.models import Country
from .utils.resolvers import resolve_association_id


class CountriesImporter(BaseImporter):
    entity = "countries"

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        # name
        name = (raw.pop("name", None) or raw.pop("Name", None) or "").strip()
        if not name:
            return False, {}
        
        nat_association = (raw.pop("nat_association", None) or raw.pop("association", None))
        if nat_association:
            nat_association = nat_association.strip() or None

        # fifa_code (normalize to upper; allow empty)
        fifa_code = (
            raw.pop("fifa_code", None)
            or raw.pop("FIFA", None)
            or raw.pop("code", None)
            or ""
        )
        fifa_code = fifa_code.strip().upper() or None

        # confederation (accept id or code/name)
        conf_token = (raw.pop("confed_ass_id", None) or raw.pop("confederation", None))
        confed_ass_id = resolve_association_id(conf_token, db)

        # sub-confederations: CSV cell like "UNAF,UAFA" (or single value)
        sub_cell = (raw.pop("sub_confederation", "") or "").strip()
        sub_tokens = [t.strip() for t in sub_cell.split(",") if t.strip()]
        sub_confed_ids: List[int] = []
        for t in sub_tokens:
            sid = resolve_association_id(t, db)  # resolves by code or name
            if sid:
                sub_confed_ids.append(sid)

        # flag filename
        flag_filename = (raw.pop("flag_filename", None) or raw.pop("flag", None) or None)
        if flag_filename:
            flag_filename = flag_filename.strip() or None

        # status
        c_status = (raw.pop("c_status", None) or raw.pop("status", None) or "active").strip().lower()
        if c_status not in ("active", "historical"):
            c_status = "active"

        return True, {
            "name": name,
            "fifa_code": fifa_code,
            "confed_ass_id": confed_ass_id,
            "flag_filename": flag_filename,
            "nat_association": nat_association,
            "c_status": c_status,
            # keep sub-confeds separate — written to junction table in upsert()
            "sub_confed_ids": list(dict.fromkeys([i for i in sub_confed_ids if i])),  # unique, non-null
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        # pull out the list for the junction table
        sub_ids: List[int] = kwargs.pop("sub_confed_ids", [])

        # upsert into country (NO sub_confed_* column here)
        stmt = (
            insert(Country)
            .values(**kwargs)
            .on_conflict_do_update(
                index_elements=["name"],  # or use fifa_code if that's your preferred natural key
                set_={
                    "flag_filename": kwargs.get("flag_filename"),
                    "fifa_code": kwargs.get("fifa_code"),
                    "confed_ass_id": kwargs.get("confed_ass_id"),
                    "nat_association": kwargs.get("nat_association"),
                    "c_status": kwargs.get("c_status"),
                    "updated_at": func.now(),
                },
            )
            .returning(Country.country_id)
        )
        country_id = db.execute(stmt).scalar_one()

        # write sub-confederations into the junction table
        country_sub_confed = Table(
            "country_sub_confed",
            Country.metadata,
            autoload_with=db.bind,
        )

        # replace links (idempotent import)
        db.execute(
            delete(country_sub_confed).where(country_sub_confed.c.country_id == country_id)
        )
        if sub_ids:
            db.execute(
                country_sub_confed.insert(),
                [{"country_id": country_id, "sub_confed_ass_id": sid} for sid in sub_ids],
            )

        return True
