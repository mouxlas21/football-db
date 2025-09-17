# backend/app/services/importers/matches.py
from typing import Dict, Any, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Match, Season, Stage, Round  # <- requires these ORM classes

def _parse_dt(val: str | None) -> datetime | None:
    if not val:
        return None
    v = str(val).strip()
    if not v:
        return None
    try:
        # Support trailing Z
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

class MatchesImporter(BaseImporter):
    """
    Accepted CSV headers (either style works):

    A) ID-based (original)
       round_id, group_id, home_team_id, away_team_id, kickoff_utc, stadium_id,
       attendance, status, home_score, away_score, winner_team_id

    B) Name-based (no round_id)
       season_name, stage_name, round_name, home_team_id, away_team_id, kickoff_utc,
       stadium_id, attendance, status, home_score, away_score, winner_team_id
    """
    entity = "matches"

    def _resolve_round_id(self, raw: Dict[str, Any], db: Session) -> int | None:
        # 1) prefer explicit round_id if provided
        rid = _to_int(raw.get("round_id"))
        if rid:
            return rid

        # 2) resolve by names: season_name + stage_name + round_name
        season_name = (raw.get("season_name") or "").strip()
        stage_name = (raw.get("stage_name") or "").strip()
        round_name = (raw.get("round_name") or "").strip()
        if not (season_name and stage_name and round_name):
            return None

        # Find the stage by joining Season -> Stage, then find Round by name
        st = db.execute(
            select(Stage)
            .join(Season, Stage.season_id == Season.season_id)
            .where(and_(Season.name == season_name, Stage.name == stage_name))
        ).scalar_one_or_none()
        if not st:
            return None

        r = db.execute(
            select(Round)
            .where(and_(Round.stage_id == st.stage_id, Round.name == round_name))
        ).scalar_one_or_none()
        return r.round_id if r else None

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        kickoff = _parse_dt(raw.get("kickoff_utc"))
        home_team_id = _to_int(raw.get("home_team_id"))
        away_team_id = _to_int(raw.get("away_team_id"))
        round_id = self._resolve_round_id(raw, db)
        group_id = _to_int(raw.get("group_id"))
        stadium_id = _to_int(raw.get("stadium_id"))
        attendance = _to_int(raw.get("attendance"))
        home_score = _to_int(raw.get("home_score")) or 0
        away_score = _to_int(raw.get("away_score")) or 0
        winner_team_id = _to_int(raw.get("winner_team_id"))
        status = (raw.get("status") or "scheduled").strip() or "scheduled"

        # required fields
        if not (kickoff and home_team_id and away_team_id and round_id):
            return False, {}

        return True, {
            "round_id": round_id,
            "group_id": group_id,
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "kickoff_utc": kickoff,
            "stadium_id": stadium_id,
            "attendance": attendance,
            "status": status,
            "home_score": home_score,
            "away_score": away_score,
            "winner_team_id": winner_team_id,
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        """
        Idempotent-ish upsert:
        - If a match with the same (round_id, home_team_id, away_team_id, kickoff_utc) exists,
          update status/scores/attendance/stadium/winner.
        - Else insert.
        """
        existing = db.execute(
            select(Match).where(
                and_(
                    Match.round_id == kwargs["round_id"],
                    Match.home_team_id == kwargs["home_team_id"],
                    Match.away_team_id == kwargs["away_team_id"],
                    Match.kickoff_utc == kwargs["kickoff_utc"],
                )
            )
        ).scalar_one_or_none()

        if existing:
            changed = False
            for f in ("status", "home_score", "away_score", "attendance", "stadium_id", "winner_team_id", "group_id"):
                v = kwargs.get(f, None)
                # let empty strings mean "no change"
                if v == "":
                    v = None
                if v is not None and getattr(existing, f) != v:
                    setattr(existing, f, v)
                    changed = True
            if changed:
                db.flush()
            return False

        # fresh insert
        stmt = insert(Match).values(**kwargs)
        res = db.execute(stmt)
        return bool(getattr(res, "rowcount", 0))
