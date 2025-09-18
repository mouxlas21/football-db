# backend/app/services/importers/fixtures.py
from typing import Dict, Any, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func, or_
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import (Fixture, Season, Stage, StageRound, StageGroup, StageGroupTeam, Competition, Team, Stadium,)

def _parse_dt(val: str | None) -> datetime | None:
    if not val:
        return None
    v = str(val).strip()
    if not v:
        return None
    try:
        # support trailing Z
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

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

class FixturesImporter(BaseImporter):
    """
    Accepted CSV headers (either style works):

    A) ID-based
       stage_round_id,group_id,home_team_id,away_team_id,kickoff_utc,stadium_id,attendance,fixture_status,home_score,away_score,winner_team_id

    B) Name-based (no stage_round_id)
       competition,season_name,stage_name,round_name,group_id,home_team_id,away_team_id,kickoff_utc,stadium_id,attendance,fixture_status,home_score,away_score,winner_team_id

    Flexible fields:
      - home_team_id / away_team_id: numeric team_id OR team name (case-insensitive)
      - stadium_id: numeric stadium_id OR stadium name (case-insensitive)
      - group_id: numeric group_id OR group name/code (resolved within the stage of the round)
      - fixture_status also accepts legacy header 'status'
    """
    entity = "fixtures"

    # ---------- resolvers ----------

    def _resolve_stage_round_id(self, raw: Dict[str, Any], db: Session) -> int | None:
        # Prefer explicit ID
        rid = _to_int(raw.get("stage_round_id"))
        if rid:
            return rid

        # Resolve by names (+ optional competition)
        comp_tok    = (raw.get("competition") or raw.get("competition_name") or "").strip()
        season_name = (raw.get("season_name") or "").strip()
        stage_name  = (raw.get("stage_name") or "").strip()
        round_name  = (raw.get("round_name") or "").strip()
        if not (season_name and stage_name and round_name):
            return None

        season_q = select(Season)
        if comp_tok:
            comp = db.execute(
                select(Competition).where(func.lower(Competition.name) == func.lower(comp_tok))
            ).scalar_one_or_none()
            if not comp:
                return None
            season_q = season_q.where(
                Season.competition_id == comp.competition_id,
                Season.name == season_name,
            )
        else:
            season_q = season_q.where(Season.name == season_name)

        se = db.execute(season_q).scalar_one_or_none()
        if not se:
            return None

        st = db.execute(
            select(Stage).where(
                Stage.season_id == se.season_id,
                func.lower(Stage.name) == func.lower(stage_name),
            )
        ).scalar_one_or_none()
        if not st:
            return None

        sr = db.execute(
            select(StageRound).where(
                StageRound.stage_id == st.stage_id,
                func.lower(StageRound.name) == func.lower(round_name),
            )
        ).scalar_one_or_none()
        return getattr(sr, "stage_round_id", None) if sr else None

    def _resolve_team_id(self, token, db: Session) -> int | None:
        """Accept numeric id or team name (case-insensitive exact)."""
        as_int = _to_int(token)
        if as_int is not None:
            return as_int
        if token is None:
            return None
        val = str(token).strip()
        if not val:
            return None
        row = db.execute(
            select(Team).where(func.lower(Team.name) == func.lower(val))
        ).scalar_one_or_none()
        return row.team_id if row else None

    def _resolve_stadium_id(self, token, db: Session) -> int | None:
        """Accept numeric id or stadium name (case-insensitive exact)."""
        as_int = _to_int(token)
        if as_int is not None:
            return as_int
        if token is None:
            return None
        val = str(token).strip()
        if not val:
            return None
        row = db.execute(
            select(Stadium).where(func.lower(Stadium.name) == func.lower(val))
        ).scalar_one_or_none()
        return row.stadium_id if row else None

    def _resolve_group_id(self, token, stage_round_id: int | None, db: Session) -> int | None:
        """Accept numeric id or group name/code, resolved within the same stage as stage_round_id."""
        as_int = _to_int(token)
        if as_int is not None:
            return as_int
        if token is None:
            return None
        val = str(token).strip()
        if not val or not stage_round_id:
            return None

        sr = db.execute(select(StageRound).where(StageRound.stage_round_id == stage_round_id)).scalar_one_or_none()
        if not sr:
            return None

        row = db.execute(
            select(StageGroup).where(
                StageGroup.stage_id == sr.stage_id,
                or_(
                    func.lower(StageGroup.name) == func.lower(val),
                    StageGroup.code == val.upper(),
                )
            )
        ).scalar_one_or_none()
        return row.group_id if row else None

    def _infer_group_id_from_membership(self, stage_round_id: int, home_team_id: int, away_team_id: int, db: Session) -> int | None:
        """If group not provided: infer the unique common group for both teams in that stage."""
        sr = db.execute(select(StageRound).where(StageRound.stage_round_id == stage_round_id)).scalar_one_or_none()
        if not sr:
            return None

        home_groups = select(StageGroup.group_id).join(StageGroupTeam, StageGroup.group_id == StageGroupTeam.group_id)\
            .where(StageGroup.stage_id == sr.stage_id, StageGroupTeam.team_id == home_team_id)

        away_groups = select(StageGroup.group_id).join(StageGroupTeam, StageGroup.group_id == StageGroupTeam.group_id)\
            .where(StageGroup.stage_id == sr.stage_id, StageGroupTeam.team_id == away_team_id)

        common = db.execute(
            select(StageGroup.group_id)
            .where(StageGroup.group_id.in_(home_groups))
            .where(StageGroup.group_id.in_(away_groups))
        ).scalars().all()

        if len(common) == 1:
            return common[0]
        return None  # ambiguous or none

    # ---------- importer API ----------

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        kickoff        = _parse_dt(raw.get("kickoff_utc"))
        stage_round_id = self._resolve_stage_round_id(raw, db)

        home_team_id   = self._resolve_team_id(raw.get("home_team_id"), db)
        away_team_id   = self._resolve_team_id(raw.get("away_team_id"), db)
        group_id       = self._resolve_group_id(raw.get("group_id"), stage_round_id, db)
        stadium_id     = self._resolve_stadium_id(raw.get("stadium_id"), db)
        attendance     = _to_int(raw.get("attendance"))
        home_score     = _to_int(raw.get("home_score")) or 0
        away_score     = _to_int(raw.get("away_score")) or 0
        winner_team_id = self._resolve_team_id(raw.get("winner_team_id"), db)
        fixture_status = (raw.get("fixture_status") or raw.get("status") or "scheduled").strip() or "scheduled"

        # Auto-infer group if missing and possible
        if group_id is None and stage_round_id and home_team_id and away_team_id:
            group_id = self._infer_group_id_from_membership(stage_round_id, home_team_id, away_team_id, db)

        # required fields
        if not (kickoff and home_team_id and away_team_id and stage_round_id):
            return False, {}

        return True, {
            "stage_round_id": stage_round_id,
            "group_id": group_id,
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "kickoff_utc": kickoff,
            "stadium_id": stadium_id,
            "attendance": attendance,
            "fixture_status": fixture_status,
            "home_score": home_score,
            "away_score": away_score,
            "winner_team_id": winner_team_id,
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        """
        Idempotent-ish upsert:
        - If a fixture with the same (stage_round_id, home_team_id, away_team_id, kickoff_utc) exists,
          update fixture_status/scores/attendance/stadium/winner/group.
        - Else insert.
        """
        existing = db.execute(
            select(Fixture).where(
                and_(
                    Fixture.stage_round_id == kwargs["stage_round_id"],
                    Fixture.home_team_id == kwargs["home_team_id"],
                    Fixture.away_team_id == kwargs["away_team_id"],
                    Fixture.kickoff_utc == kwargs["kickoff_utc"],
                )
            )
        ).scalar_one_or_none()

        if existing:
            changed = False
            for f in ("fixture_status", "home_score", "away_score", "attendance", "stadium_id", "winner_team_id", "group_id"):
                v = kwargs.get(f, None)
                if v == "":
                    v = None
                if v is not None and getattr(existing, f) != v:
                    setattr(existing, f, v)
                    changed = True
            if changed:
                db.flush()
            return False

        res = db.execute(insert(Fixture).values(**kwargs))
        return bool(getattr(res, "rowcount", 0))
