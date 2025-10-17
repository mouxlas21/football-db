from typing import Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Competition, Association
from .utils.helpers import _to_int
import re, unicodedata

class CompetitionsImporter(BaseImporter):
    """
    Accepts CSV headers:
      association,country,name,type,tier,cup_rank,gender,age_group,status,notes,logo_filename

    - association: ID | CODE (UEFA/FIFA/DFB/CAF/...) | full name (case-insensitive)
    - country:     ID | FIFA code (GER/ENG/...) | country name (case-insensitive)
    """

    entity = "competitions"

    # ---------- simple utils ----------

    def _slugify(self, s: str) -> str:
        nfkd = unicodedata.normalize("NFKD", s)
        s = nfkd.encode("ascii", "ignore").decode("ascii")
        s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
        return s

    def _parse_tier(self, token: Optional[str]) -> Optional[int]:
        if not token or not str(token).strip():
            return None
        m = re.search(r"(\d+)", str(token))
        return int(m.group(1)) if m else None

    # ---------- resolvers (reuse your previous approach) ----------

    def _resolve_ass(self, token: str | None, db: Session) -> tuple[Optional[int], Optional[str]]:
        """Return (ass_id, ass_code_lower)."""
        if token is None or str(token).strip() == "":
            return None, None
        as_int = _to_int(token)
        if as_int is not None:
            row = db.execute(select(Association).where(Association.ass_id == as_int)).scalar_one_or_none()
            return (row.ass_id, (row.code or "").lower()) if row else (None, None)

        val = str(token).strip()
        # by CODE
        row = db.execute(select(Association).where(Association.code == val.upper())).scalar_one_or_none()
        if row:
            return row.ass_id, (row.code or "").lower()
        # by NAME (case-insensitive exact)
        row = db.execute(select(Association).where(func.lower(Association.name) == func.lower(val))).scalar_one_or_none()
        if row:
            return row.ass_id, (row.code or "").lower()
        return None, None

    def _resolve_country(self, token: str | None, db: Session) -> tuple[Optional[int], Optional[str]]:
        """Return (country_id, country_slug_lower)."""
        if token is None or str(token).strip() == "":
            return None, None
        as_int = _to_int(token)
        from app.models import Country
        if as_int is not None:
            row = db.execute(select(Country).where(Country.country_id == as_int)).scalar_one_or_none()
            if not row: return None, None
            return row.country_id, self._slugify(row.name)

        val = str(token).strip()
        # by FIFA code
        row = db.execute(select(Country).where(Country.fifa_code == val.upper())).scalar_one_or_none()
        if row:
            return row.country_id, self._slugify(row.name)
        # by NAME (case-insensitive exact)
        row = db.execute(select(Country).where(func.lower(Country.name) == func.lower(val))).scalar_one_or_none()
        if row:
            return row.country_id, self._slugify(row.name)
        return None, None

    # ---------- importer hooks ----------

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        name = (raw.get("name") or "").strip()
        ctype = (raw.get("type") or "").strip().lower()
        if not name or not ctype:
            return False, {}

        organizer_ass_id, organizer_code = self._resolve_ass(raw.get("association"), db)
        country_id, country_slug = self._resolve_country(raw.get("country"), db)

        # slug strategy: country prefix if available, else association code
        base = self._slugify(name)
        prefix = country_slug or organizer_code or ""
        slug = f"{prefix}_{base}" if prefix else base

        tier = self._parse_tier(raw.get("tier"))

        # normalize 'cup_rank' -> domain
        cup_rank = (raw.get("cup_rank") or "").strip().lower()
        gender = (raw.get("gender") or None)
        age_group = (raw.get("age_group") or None)
        status = (raw.get("status") or None) or "active"
        notes = (raw.get("notes") or None)

        logo_filename = (raw.get("logo_filename") or raw.get("logo") or None)
        if logo_filename:
            logo_filename = logo_filename.strip() or None

        return True, {
            "slug": slug,
            "name": name,
            "type": ctype,
            "tier": tier,
            "cup_rank": cup_rank,
            "gender": gender,
            "age_group": age_group,
            "status": status,
            "notes": notes,
            "logo_filename": logo_filename,
            "country_id": country_id,
            "organizer_ass_id": organizer_ass_id,
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        stmt = (
            insert(Competition)
            .values(**kwargs)
            .on_conflict_do_update(
                index_elements=["slug"],
                set_={
                    "name": kwargs["name"],
                    "type": kwargs["type"],
                    "tier": kwargs["tier"],
                    "cup_rank": kwargs["cup_rank"],
                    "gender": kwargs["gender"],
                    "age_group": kwargs["age_group"],
                    "status": kwargs["status"],
                    "notes": kwargs["notes"],
                    "logo_filename": kwargs.get("logo_filename"),
                    "country_id": kwargs["country_id"],
                    "organizer_ass_id": kwargs["organizer_ass_id"],
                    "updated_at": func.now(),
                },
            )
        )
        res = db.execute(stmt)
        return bool(getattr(res, "rowcount", 0))