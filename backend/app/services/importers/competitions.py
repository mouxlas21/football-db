from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Competition, Association, Country

def _to_int(val):
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    try:
        return int(s)
    except Exception:
        return None

class CompetitionsImporter(BaseImporter):
    """
    CSV headers (supported):
      name,type,organizer,country_id,confederation

    - organizer: ID (e.g. 1) OR code (UEFA/FIFA/DFB/…) OR full name (case-insensitive)
    - country_id: ID OR FIFA code (GER/ENG/…) OR country name (case-insensitive)
    - confederation: (optional) code or name; used only to validate against organizer's lineage
    """
    entity = "competitions"

    # ------- resolvers -------

    def _resolve_ass_id(self, token: str | None, db: Session) -> int | None:
        """Resolve association by ID, code (upper), or name (case-insensitive)."""
        if token is None:
            return None
        as_int = _to_int(token)
        if as_int is not None:
            return as_int
        val = str(token).strip()
        if not val:
            return None
        # by code (upper)
        code = val.upper()
        row = db.execute(select(Association).where(Association.code == code)).scalar_one_or_none()
        if row:
            return row.ass_id
        # by name (case-insensitive exact)
        row = db.execute(
            select(Association).where(func.lower(Association.name) == func.lower(val))
        ).scalar_one_or_none()
        if row:
            return row.ass_id
        return None

    def _resolve_country_id(self, token: str | None, db: Session) -> int | None:
        """Resolve country by ID, FIFA code (upper), or name (case-insensitive)."""
        if token is None:
            return None
        as_int = _to_int(token)
        if as_int is not None:
            return as_int
        val = str(token).strip()
        if not val:
            return None
        # by FIFA code (upper)
        from app.models import Country
        fifa = val.upper()
        row = db.execute(select(Country).where(Country.fifa_code == fifa)).scalar_one_or_none()
        if row:
            return row.country_id
        # by name (case-insensitive exact)
        row = db.execute(
            select(Country).where(func.lower(Country.name) == func.lower(val))
        ).scalar_one_or_none()
        if row:
            return row.country_id
        return None

    def _derive_confed_from_org(self, org_id: int | None, db: Session) -> int | None:
        """Walk parent_org_id until we hit a confederation level (UEFA/CONMEBOL/...)."""
        if not org_id:
            return None
        confed_codes = {"UEFA", "CONMEBOL", "CONCACAF", "AFC", "CAF", "OFC"}
        seen = set()
        cur = org_id
        while cur and cur not in seen:
            seen.add(cur)
            row = db.execute(select(Association).where(Association.ass_id == cur)).scalar_one_or_none()
            if not row:
                return None
            if row.level == "confederation" or (row.code and row.code.upper() in confed_codes):
                return row.ass_id
            cur = row.parent_org_id
        # Optionally treat FIFA as its own "global confederation"
        # if row and row.code == "FIFA": return row.ass_id
        return None

    # ------- importer hooks -------

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        name = (raw.pop("name", None) or "").strip()
        ctype = (raw.pop("type", None) or "").strip().lower()
        if not name or not ctype:
            return False, {}

        organizer_token = raw.pop("organizer", None)      # id | code | name
        country_token   = raw.pop("country_id", None)     # id | fifa | name
        confed_token    = raw.pop("confederation", None)  # optional validation only

        organizer_ass_id = self._resolve_ass_id(organizer_token, db)
        country_id = self._resolve_country_id(country_token, db)

        # validate confederation hint (if provided)
        derived_confed_id = self._derive_confed_from_org(organizer_ass_id, db)
        if confed_token:
            hinted_confed_id = self._resolve_ass_id(confed_token, db)
            if hinted_confed_id and derived_confed_id and hinted_confed_id != derived_confed_id:
                self.log_warn(f"[competitions] '{name}': confederation hint '{confed_token}' "
                              f"!= organizer lineage (derived id={derived_confed_id})")

        return True, {
            "name": name,
            "type": ctype,
            "organizer_ass_id": organizer_ass_id,  # <-- the new canonical FK
            "country_id": country_id,
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        """
        Unique by name (per your schema). If you ever relax that, consider (name, type).
        """
        stmt = (
            insert(Competition)
            .values(**kwargs)
            .on_conflict_do_update(
                index_elements=["name"],
                set_={
                    "type": kwargs["type"],
                    "organizer_ass_id": kwargs["organizer_ass_id"],
                    "country_id": kwargs["country_id"],
                },
            )
        )
        res = db.execute(stmt)
        # rowcount>0 indicates an INSERT happened; UPDATEs can be reported as False if you want.
        return bool(getattr(res, "rowcount", 0))
