from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import StageGroup, Stage, Season, Competition
from .utils.helpers import _to_int

class StageGroupsImporter(BaseImporter):
    entity = "stage_groups"

    def _resolve_stage_id(self, token, db: Session, ctx: Dict[str, Any]) -> int | None:
        """
        Resolve stage_id either directly from an integer, or by (competition, season_name, stage_name).
        ctx can include: competition | competition_name, season_id | season_name, stage_name
        """
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

        # Accept stage via multiple styles:
        ctx = {
            "competition": raw.get("competition") or raw.get("competition_name"),
            "season_name": raw.get("season_name") or raw.get("season_id"),  # season_id may be a name like 2024/25
            "stage_name": raw.get("stage_name"),
        }
        stage_id = self._resolve_stage_id(raw.get("stage_id"), db, ctx)
        if not stage_id:
            return False, {}

        code = (raw.get("code") or "").strip() or None

        return True, {"stage_id": stage_id, "name": name, "code": code}

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        existing = db.execute(
            select(StageGroup).where(
                StageGroup.stage_id == kwargs["stage_id"],
                func.lower(StageGroup.name) == func.lower(kwargs["name"])
            )
        ).scalar_one_or_none()

        if existing:
            changed = False
            if kwargs.get("code") is not None and existing.code != kwargs["code"]:
                existing.code = kwargs["code"]
                changed = True
            if changed:
                db.flush()
            return False

        res = db.execute(insert(StageGroup).values(**kwargs))
        return bool(getattr(res, "rowcount", 0))
