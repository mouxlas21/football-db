from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import StageRound, Stage, Season, Competition
from .utils.helpers import _to_int, _to_bool

class StageRoundsImporter(BaseImporter):
    entity = "stage_rounds"

    def _resolve_stage_id(self, token, db: Session, ctx: Dict[str, Any]) -> int | None:
        sid = _to_int(token)
        if sid is not None:
            return sid

        comp_tok = ctx.get("competition") or ctx.get("competition_name")
        season_tok = ctx.get("season_name") or ctx.get("season_id")
        stage_name = ctx.get("stage_name")
        if not (comp_tok and season_tok and stage_name):
            return None

        comp = db.execute(
            select(Competition).where(func.lower(Competition.name) == func.lower(str(comp_tok).strip()))
        ).scalar_one_or_none()
        if not comp:
            return None

        season = db.execute(
            select(Season).where(
                and_(Season.competition_id == comp.competition_id,
                     Season.name == str(season_tok).strip())
            )
        ).scalar_one_or_none()
        if not season:
            return None

        stage = db.execute(
            select(Stage).where(
                and_(Stage.season_id == season.season_id,
                     func.lower(Stage.name) == func.lower(str(stage_name).strip()))
            )
        ).scalar_one_or_none()
        return stage.stage_id if stage else None

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        name = (raw.get("name") or "").strip()
        if not name:
            return False, {}

        ctx = {
            "competition": raw.get("competition") or raw.get("competition_name"),
            "season_name": raw.get("season_name") or raw.get("season_id"),
            "stage_name": raw.get("stage_name"),
        }
        stage_id = self._resolve_stage_id(raw.get("stage_id"), db, ctx)
        if not stage_id:
            return False, {}

        stage_round_order = _to_int(raw.get("stage_round_order")) or _to_int(raw.get("round_order")) or 1
        two_legs = _to_bool(raw.get("two_legs"))

        return True, {
            "stage_id": stage_id,
            "name": name,
            "stage_round_order": stage_round_order,
            "two_legs": two_legs,
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        existing = db.execute(
            select(StageRound).where(
                StageRound.stage_id == kwargs["stage_id"],
                func.lower(StageRound.name) == func.lower(kwargs["name"])
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

        res = db.execute(insert(StageRound).values(**kwargs))
        return bool(getattr(res, "rowcount", 0))
