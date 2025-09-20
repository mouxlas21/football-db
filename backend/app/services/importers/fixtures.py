from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func, or_
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import (Fixture, Season, Stage, Club, StageRound, StageGroup, StageGroupTeam, Competition,Team, Stadium,)
from .utils.helpers import _to_int, _to_bool, _parse_dt, _decide_winner



class FixturesImporter(BaseImporter):
    """
    Accepted CSV headers (either style works):

    A) ID-based
       stage_round_id,group_id,home_team_id,away_team_id,kickoff_utc,stadium_id,attendance,fixture_status,
       ht_home_score,ht_away_score,ft_home_score,ft_away_score,et_home_score,et_away_score,pen_home_score,pen_away_score,
       went_to_extra_time,went_to_penalties,home_score,away_score,winner_team_id

    B) Name-based (no stage_round_id)
       competition,season_name,stage_name,round_name,group_id,home_team_id,away_team_id,kickoff_utc,stadium_id,attendance,fixture_status,
       ht_home_score,ht_away_score,ft_home_score,ft_away_score,et_home_score,et_away_score,pen_home_score,pen_away_score,
       went_to_extra_time,went_to_penalties,home_score,away_score,winner_team_id

    Flexible fields:
      - home_team_id / away_team_id: numeric team_id OR team name (case-insensitive)
      - stadium_id: numeric stadium_id OR stadium name (case-insensitive)
      - group_id: numeric group_id OR group name/code (resolved within the stage of the round)
      - fixture_status also accepts legacy header 'status'
    """
    entity = "fixtures"

    # ---------- resolvers ----------

    def _resolve_stage_round_id(self, raw: Dict[str, Any], db: Session) -> int | None:
        rid = _to_int(raw.get("stage_round_id"))
        if rid:
            return rid

        comp_tok    = (raw.get("competition") or raw.get("competition_name") or "").strip()
        season_name = (raw.get("season") or raw.get("season_name") or "").strip()
        stage_name  = (raw.get("stage") or raw.get("stage_name") or "").strip()
        round_name  = (raw.get("round") or raw.get("round_name") or "").strip()
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
        kickoff        = _parse_dt(raw.get("kickoff_utc") or raw.get("kickoff"))
        stage_round_id = self._resolve_stage_round_id(raw, db)

        home_team_id   = self._resolve_team_id(raw.get("home_team_id") or raw.get("home_team") or raw.get("home"), db)
        away_team_id   = self._resolve_team_id(raw.get("away_team_id") or raw.get("away_team") or raw.get("away"), db)
        group_id       = self._resolve_group_id(raw.get("group_id") or raw.get("group"), stage_round_id, db)

        # Try CSV stadium (id or name). It's fine if the header doesn't exist.
        stadium_id     = self._resolve_stadium_id(raw.get("stadium_id") or raw.get("stadium") or "", db)

        attendance     = _to_int(raw.get("attendance"))

        # period splits (all optional)
        ht_home = _to_int(raw.get("ht_home_score"))
        ht_away = _to_int(raw.get("ht_away_score"))
        ft_home = _to_int(raw.get("ft_home_score"))
        ft_away = _to_int(raw.get("ft_away_score"))
        et_home = _to_int(raw.get("et_home_score"))
        et_away = _to_int(raw.get("et_away_score"))
        pen_home = _to_int(raw.get("pen_home_score"))
        pen_away = _to_int(raw.get("pen_away_score"))

        # flow flags (optional; infer if omitted)
        went_et  = _to_bool(raw.get("went_to_extra_time") or raw.get("extra_time"), default=None)
        went_pen = _to_bool(raw.get("went_to_penalties") or raw.get("penalties"), default=None)

        if went_et is None:
            went_et = (et_home is not None and et_away is not None)
        if went_pen is None:
            went_pen = (pen_home is not None and pen_away is not None)

        # explicit final scores (optional; may compute below)
        csv_home_final = _to_int(raw.get("home_score"))
        csv_away_final = _to_int(raw.get("away_score"))

        # derive final score: ET > FT > explicit > default 0
        if et_home is not None and et_away is not None:
            home_final, away_final = et_home, et_away
        elif ft_home is not None and ft_away is not None:
            home_final, away_final = ft_home, ft_away
        elif csv_home_final is not None and csv_away_final is not None:
            home_final, away_final = csv_home_final, csv_away_final
        else:
            home_final, away_final = 0, 0

        # status + auto-played (fix precedence)
        fixture_status = (raw.get("fixture_status") or raw.get("status") or "scheduled").strip() or "scheduled"
        if fixture_status == "scheduled" and (
            (ft_home is not None and ft_away is not None) or
            (et_home is not None and et_away is not None)
        ):
            fixture_status = "played"

        # winner (explicit or infer)
        winner_team_id = self._resolve_team_id(raw.get("winner_team_id") or raw.get("winner") or raw.get("winner_name"), db)
        if winner_team_id is None:
            winner_team_id = _decide_winner(home_team_id, away_team_id, home_final, away_final, bool(went_pen), pen_home, pen_away)

        # Auto-infer group if missing and possible
        if group_id is None and stage_round_id and home_team_id and away_team_id:
            group_id = self._infer_group_id_from_membership(stage_round_id, home_team_id, away_team_id, db)

        # If stadium still missing, try to infer from the home team's club
        if not stadium_id and home_team_id:
            team = db.execute(select(Team).where(Team.team_id == home_team_id)).scalar_one_or_none()
            if team and team.club_id:
                club = db.execute(select(Club).where(Club.club_id == team.club_id)).scalar_one_or_none()
                stadium_id = getattr(club, "stadium_id", None)

        # required fields
        if not (kickoff and home_team_id and away_team_id and stage_round_id):
            return False, {}

        # Build payload, OMIT stadium_id if unresolved (None/falsey)
        payload: Dict[str, Any] = {
            "stage_round_id": stage_round_id,
            "group_id": group_id,
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "kickoff_utc": kickoff,
            "attendance": attendance,
            "fixture_status": fixture_status,

            # period splits
            "ht_home_score": ht_home,
            "ht_away_score": ht_away,
            "ft_home_score": ft_home,
            "ft_away_score": ft_away,
            "et_home_score": et_home,
            "et_away_score": et_away,
            "pen_home_score": pen_home,
            "pen_away_score": pen_away,

            # flow flags
            "went_to_extra_time": bool(went_et),
            "went_to_penalties": bool(went_pen),

            # final
            "home_score": home_final,
            "away_score": away_final,

            "winner_team_id": winner_team_id,
        }
        if stadium_id:
            payload["stadium_id"] = stadium_id

        return True, payload

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
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
            for f in (
                "fixture_status", "attendance", "stadium_id", "winner_team_id", "group_id",
                "ht_home_score","ht_away_score","ft_home_score","ft_away_score",
                "et_home_score","et_away_score","pen_home_score","pen_away_score",
                "went_to_extra_time","went_to_penalties",
                "home_score","away_score",
            ):
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
