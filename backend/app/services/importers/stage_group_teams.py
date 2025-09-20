from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Competition, Season, Stage, StageGroup, Team, StageGroupTeam
from .utils.helpers import _to_int

class StageGroupTeamsImporter(BaseImporter):
    """
    CSV headers (either style):
      A) group_id, team_id
      B) competition, season_name, stage_name, group, team

    - group: name ("Group A") or code ("A")
    - team: id or exact team name (case-insensitive)
    """
    entity = "stage_group_teams"

    def _resolve_team_id(self, token, db: Session) -> int | None:
        as_int = _to_int(token)
        if as_int is not None:
            return as_int
        if token is None: return None
        val = str(token).strip()
        if not val: return None
        row = db.execute(select(Team).where(func.lower(Team.name) == func.lower(val))).scalar_one_or_none()
        return row.team_id if row else None

    def _resolve_group_id(self, raw: Dict[str, Any], db: Session) -> int | None:
        gid = _to_int(raw.get("group_id"))
        if gid is not None:
            return gid

        comp = (raw.get("competition") or "").strip()
        season_name = (raw.get("season_name") or "").strip()
        stage_name = (raw.get("stage_name") or "").strip()
        group_tok = (raw.get("group") or "").strip()
        if not (comp and season_name and stage_name and group_tok):
            return None

        c = db.execute(select(Competition).where(func.lower(Competition.name) == func.lower(comp))).scalar_one_or_none()
        if not c: return None

        se = db.execute(select(Season).where(and_(Season.competition_id == c.competition_id, Season.name == season_name))).scalar_one_or_none()
        if not se: return None

        st = db.execute(select(Stage).where(and_(Stage.season_id == se.season_id, func.lower(Stage.name) == func.lower(stage_name)))).scalar_one_or_none()
        if not st: return None

        g = db.execute(
            select(StageGroup).where(
                StageGroup.stage_id == st.stage_id,
                or_(func.lower(StageGroup.name) == func.lower(group_tok), StageGroup.code == group_tok.upper())
            )
        ).scalar_one_or_none()
        return g.group_id if g else None

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        group_id = self._resolve_group_id(raw, db)
        team_id = self._resolve_team_id(raw.get("team") or raw.get("team_id"), db)
        if not (group_id and team_id):
            return False, {}
        return True, {"group_id": group_id, "team_id": team_id}

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        stmt = (
            insert(StageGroupTeam)
            .values(**kwargs)
            .on_conflict_do_nothing(index_elements=["group_id", "team_id"])
        )
        res = db.execute(stmt)
        return bool(getattr(res, "rowcount", 0))
