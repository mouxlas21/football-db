# backend/app/services/importers/stage_rounds.py
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import StageRound


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


def _to_bool(v):
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ("1", "true", "t", "yes", "y")


class StageRoundsImporter(BaseImporter):
    entity = "stage_rounds"

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        name = (raw.get("name") or "").strip()
        if not name:
            return False, {}

        stage_id = _to_int(raw.get("stage_id"))
        if not stage_id:
            return False, {}

        stage_round_order = _to_int(raw.get("stage_round_order")) or 1
        two_legs = _to_bool(raw.get("two_legs"))

        return True, {
            "stage_id": stage_id,
            "name": name,
            "stage_round_order": stage_round_order,
            "two_legs": two_legs,
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        # Check if this stage_round already exists
        existing = db.execute(
            StageRound.__table__.select().where(
                StageRound.stage_id == kwargs["stage_id"],
                StageRound.name == kwargs["name"]
            )
        ).scalar_one_or_none()

        if existing:
            changed = False
            for f in ("stage_round_order", "two_legs"):
                v = kwargs.get(f)
                if v is not None and getattr(existing, f) != v:
                    setattr(existing, f, v)
                    changed = True
            if changed:
                db.flush()
            return False

        stmt = insert(StageRound).values(**kwargs)
        res = db.execute(stmt)
        return bool(getattr(res, "rowcount", 0))
