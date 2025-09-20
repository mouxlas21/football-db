from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, select
from ..db import get_db
from ..core.templates import templates
from ..models import Season, Stage

router = APIRouter(prefix="/competitions/{comp_id}/seasons/{season_id}/league", tags=["league"])

def _get_league_stage_id(db: Session, season_id: int) -> int:
    """
    Return the stage_id of the league-format stage for this season.
    Pick the first stage with format='league' (or fallback to lowest stage_order).
    """
    # Prefer declared format='league'
    row = db.execute(
        select(Stage.stage_id)
        .where(Stage.season_id == season_id)
        .where(Stage.format.ilike("league"))
        .order_by(Stage.stage_order.asc())
        .limit(1)
    ).scalar_one_or_none()
    if row:
        return int(row)

    # Fallback: just take the first stage in order
    row = db.execute(
        select(Stage.stage_id)
        .where(Stage.season_id == season_id)
        .order_by(Stage.stage_order.asc())
        .limit(1)
    ).scalar_one_or_none()

    if not row:
        raise HTTPException(404, "No stage found for this season")
    return int(row)

@router.get("/table", response_class=HTMLResponse)
def league_table(comp_id: int, season_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Compute a classic 3-1-0 league table for fixtures of this season where FT scores exist.
    Uses: fixture.ft_home_score / ft_away_score as the final result.
    """
    # Ensure season exists & belongs to comp
    season = db.execute(
        select(Season).where(Season.season_id == season_id, Season.competition_id == comp_id)
    ).scalar_one_or_none()
    if not season:
        raise HTTPException(404, "Season not found for this competition")

    sql = text("""
        WITH season_fixtures AS (
          SELECT f.*
          FROM fixture f
          JOIN stage_round sr ON sr.stage_round_id = f.stage_round_id
          JOIN stage s ON s.stage_id = sr.stage_id
          JOIN season se ON se.season_id = s.season_id
          WHERE se.season_id = :season_id
            AND f.ft_home_score IS NOT NULL
            AND f.ft_away_score IS NOT NULL
        ),
        home AS (
          SELECT home_team_id AS team_id,
                 COUNT(*) AS pld,
                 SUM(CASE WHEN ft_home_score > ft_away_score THEN 1 ELSE 0 END) AS w,
                 SUM(CASE WHEN ft_home_score = ft_away_score THEN 1 ELSE 0 END) AS d,
                 SUM(CASE WHEN ft_home_score < ft_away_score THEN 1 ELSE 0 END) AS l,
                 SUM(ft_home_score) AS gf,
                 SUM(ft_away_score) AS ga
          FROM season_fixtures
          GROUP BY home_team_id
        ),
        away AS (
          SELECT away_team_id AS team_id,
                 COUNT(*) AS pld,
                 SUM(CASE WHEN ft_away_score > ft_home_score THEN 1 ELSE 0 END) AS w,
                 SUM(CASE WHEN ft_away_score = ft_home_score THEN 1 ELSE 0 END) AS d,
                 SUM(CASE WHEN ft_away_score < ft_home_score THEN 1 ELSE 0 END) AS l,
                 SUM(ft_away_score) AS gf,
                 SUM(ft_home_score) AS ga
          FROM season_fixtures
          GROUP BY away_team_id
        ),
        agg AS (
          SELECT COALESCE(h.team_id, a.team_id) AS team_id,
                 COALESCE(h.pld,0) + COALESCE(a.pld,0) AS pld,
                 COALESCE(h.w,0)   + COALESCE(a.w,0)   AS w,
                 COALESCE(h.d,0)   + COALESCE(a.d,0)   AS d,
                 COALESCE(h.l,0)   + COALESCE(a.l,0)   AS l,
                 COALESCE(h.gf,0)  + COALESCE(a.gf,0)  AS gf,
                 COALESCE(h.ga,0)  + COALESCE(a.ga,0)  AS ga
          FROM home h
          FULL OUTER JOIN away a ON a.team_id = h.team_id
        )
        SELECT t.team_id, t.name,
               a.pld, a.w, a.d, a.l, a.gf, a.ga,
               (a.gf - a.ga) AS gd,
               (a.w*3 + a.d) AS pts
        FROM agg a
        JOIN team t ON t.team_id = a.team_id
        ORDER BY pts DESC, gd DESC, gf DESC, t.name ASC;
    """)
    rows = db.execute(sql, {"season_id": season_id}).mappings().all()

    return templates.TemplateResponse(
        "league_table.html",
        {"request": request, "competition_id": comp_id, "season_id": season_id, "table": rows},
    )

@router.get("/matchday/{n}", response_class=HTMLResponse)
def league_matchday(comp_id: int, season_id: int, n: int, request: Request, db: Session = Depends(get_db)):
    """
    Show fixtures for matchday n (stage_round.stage_round_order = n) of the league stage of this season.
    """
    # Validate season and get the league stage id
    season = db.execute(
        select(Season).where(Season.season_id == season_id, Season.competition_id == comp_id)
    ).scalar_one_or_none()
    if not season:
        raise HTTPException(404, "Season not found for this competition")

    league_stage_id = _get_league_stage_id(db, season_id)

    fixtures_sql = text("""
        SELECT f.fixture_id, f.kickoff_utc, f.fixture_status,
               f.ft_home_score, f.ft_away_score,
               th.team_id AS home_team_id, th.name AS home_name,
               ta.team_id AS away_team_id, ta.name AS away_name
        FROM fixture f
        JOIN stage_round sr ON sr.stage_round_id = f.stage_round_id
        JOIN team th ON th.team_id = f.home_team_id
        JOIN team ta ON ta.team_id = f.away_team_id
        WHERE sr.stage_id = :stage_id
          AND sr.stage_round_order = :n
        ORDER BY f.kickoff_utc ASC, f.fixture_id ASC;
    """)
    fixtures = db.execute(fixtures_sql, {"stage_id": league_stage_id, "n": n}).mappings().all()
    if not fixtures:
        raise HTTPException(404, f"No fixtures for matchday {n}")

    # total matchdays for this league stage
    total_sql = text("SELECT COUNT(*) FROM stage_round WHERE stage_id = :stage_id;")
    total_matchdays = db.execute(total_sql, {"stage_id": league_stage_id}).scalar_one()

    return templates.TemplateResponse(
        "league_matchday.html",
        {
            "request": request,
            "competition_id": comp_id,
            "season_id": season_id,
            "n": n,
            "total_matchdays": total_matchdays,
            "fixtures": fixtures,
        },
    )
@router.get("/overview", response_class=HTMLResponse)
def league_overview(
    comp_id: int,
    season_id: int,
    request: Request,
    md: int | None = Query(default=None, description="Matchday to preview; default = last completed"),
    db: Session = Depends(get_db),
):
    # Validate season
    season = db.execute(
        select(Season).where(Season.season_id == season_id, Season.competition_id == comp_id)
    ).scalar_one_or_none()
    if not season:
        raise HTTPException(404, "Season not found for this competition")

    # Identify league stage
    league_stage_id = _get_league_stage_id(db, season_id)

    # Total matchdays
    total_matchdays = db.execute(
        text("SELECT COUNT(*) FROM stage_round WHERE stage_id = :sid"), {"sid": league_stage_id}
    ).scalar_one()

    # Choose default md = last matchday that has any FT score present
    if md is None:
        last_md = db.execute(text("""
            SELECT COALESCE(MAX(sr.stage_round_order), 1)
            FROM stage_round sr
            JOIN fixture f ON f.stage_round_id = sr.stage_round_id
            WHERE sr.stage_id = :sid
              AND f.ft_home_score IS NOT NULL
              AND f.ft_away_score IS NOT NULL
        """), {"sid": league_stage_id}).scalar_one()
        md = last_md or 1

    # ---- Final standings (snapshot if exists; else compute full season) ----
    has_snapshot = db.execute(text("""
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
          WHERE table_name = 'league_table_snapshot'
        )
    """)).scalar_one()

    if has_snapshot:
        final_rows = db.execute(text("""
            SELECT lts.position, t.name, lts.played, lts.wins, lts.draws, lts.losses,
                   lts.goals_for AS gf, lts.goals_against AS ga, lts.goal_diff AS gd,
                   lts.points AS pts, lts.notes
            FROM league_table_snapshot lts
            JOIN team t ON t.team_id = lts.team_id
            WHERE lts.season_id = :season_id
            ORDER BY lts.position ASC, t.name ASC
        """), {"season_id": season_id}).mappings().all()
    else:
        final_rows = _compute_standings(db, season_id, up_to_matchday=None)  # all MDs

    # ---- Fixtures for selected matchday ----
    fixtures = db.execute(text("""
        SELECT f.fixture_id, f.kickoff_utc, f.fixture_status,
               f.ft_home_score, f.ft_away_score,
               th.name AS home_name, ta.name AS away_name
        FROM fixture f
        JOIN stage_round sr ON sr.stage_round_id = f.stage_round_id
        JOIN team th ON th.team_id = f.home_team_id
        JOIN team ta ON ta.team_id = f.away_team_id
        WHERE sr.stage_id = :sid AND sr.stage_round_order = :n
        ORDER BY f.kickoff_utc ASC, f.fixture_id ASC
    """), {"sid": league_stage_id, "n": md}).mappings().all()

    # ---- Standings as of selected matchday ----
    md_rows = _compute_standings(db, season_id, up_to_matchday=md)

    return templates.TemplateResponse(
        "league_overview.html",
        {
            "request": request,
            "competition_id": comp_id,
            "season_id": season_id,
            "total_matchdays": total_matchdays,
            "selected_md": md,
            "final_rows": final_rows,
            "fixtures": fixtures,
            "md_rows": md_rows,
        },
    )


def _get_points_rule(db: Session, season_id: int) -> tuple[int, int, int]:
    row = db.execute(text("""
        SELECT win_points, draw_points, loss_points
        FROM season_points_rule
        WHERE season_id = :sid
    """), {"sid": season_id}).first()
    return (row[0], row[1], row[2]) if row else (3, 1, 0)


def _get_points_adjustments(db: Session, season_id: int) -> dict[int, int]:
    has_table = db.execute(text("""
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
          WHERE table_name = 'league_points_adjustment'
        )
    """)).scalar_one()
    if not has_table:
        return {}
    rows = db.execute(text("""
        SELECT team_id, COALESCE(SUM(points_delta),0) AS delta
        FROM league_points_adjustment
        WHERE season_id = :sid
        GROUP BY team_id
    """), {"sid": season_id}).mappings().all()
    return {r["team_id"]: r["delta"] for r in rows}


def _compute_standings(db: Session, season_id: int, up_to_matchday: int | None):
    # Points rule
    win_pts, draw_pts, loss_pts = _get_points_rule(db, season_id)
    # Up-to filter (for "as-of matchday")
    md_filter = "TRUE" if up_to_matchday is None else "sr.stage_round_order <= :md"

    sql = text(f"""
        WITH season_fixtures AS (
          SELECT f.*, sr.stage_round_order
          FROM fixture f
          JOIN stage_round sr ON sr.stage_round_id = f.stage_round_id
          JOIN stage s ON s.stage_id = sr.stage_id
          JOIN season se ON se.season_id = s.season_id
          WHERE se.season_id = :season_id
            AND f.ft_home_score IS NOT NULL
            AND f.ft_away_score IS NOT NULL
            AND {md_filter}
        ),
        home AS (
          SELECT home_team_id AS team_id,
                 COUNT(*) AS pld,
                 SUM(CASE WHEN ft_home_score > ft_away_score THEN 1 ELSE 0 END) AS w,
                 SUM(CASE WHEN ft_home_score = ft_away_score THEN 1 ELSE 0 END) AS d,
                 SUM(CASE WHEN ft_home_score < ft_away_score THEN 1 ELSE 0 END) AS l,
                 SUM(ft_home_score) AS gf,
                 SUM(ft_away_score) AS ga
          FROM season_fixtures
          GROUP BY home_team_id
        ),
        away AS (
          SELECT away_team_id AS team_id,
                 COUNT(*) AS pld,
                 SUM(CASE WHEN ft_away_score > ft_home_score THEN 1 ELSE 0 END) AS w,
                 SUM(CASE WHEN ft_away_score = ft_home_score THEN 1 ELSE 0 END) AS d,
                 SUM(CASE WHEN ft_away_score < ft_home_score THEN 1 ELSE 0 END) AS l,
                 SUM(ft_away_score) AS gf,
                 SUM(ft_home_score) AS ga
          FROM season_fixtures
          GROUP BY away_team_id
        ),
        agg AS (
          SELECT COALESCE(h.team_id, a.team_id) AS team_id,
                 COALESCE(h.pld,0) + COALESCE(a.pld,0) AS pld,
                 COALESCE(h.w,0)   + COALESCE(a.w,0)   AS w,
                 COALESCE(h.d,0)   + COALESCE(a.d,0)   AS d,
                 COALESCE(h.l,0)   + COALESCE(a.l,0)   AS l,
                 COALESCE(h.gf,0)  + COALESCE(a.gf,0)  AS gf,
                 COALESCE(h.ga,0)  + COALESCE(a.ga,0)  AS ga
          FROM home h
          FULL OUTER JOIN away a ON a.team_id = h.team_id
        ),
        base AS (
          SELECT a.team_id, t.name,
                 a.pld, a.w, a.d, a.l, a.gf, a.ga,
                 (a.gf - a.ga) AS gd,
                 (a.w * :win_pts + a.d * :draw_pts + a.l * :loss_pts) AS pts
          FROM agg a
          JOIN team t ON t.team_id = a.team_id
        ),
        adjusted AS (
          SELECT b.team_id, b.name, b.pld, b.w, b.d, b.l, b.gf, b.ga, b.gd,
                 (b.pts + COALESCE(adj.delta,0)) AS pts
          FROM base b
          LEFT JOIN (
            SELECT team_id, SUM(points_delta) AS delta
            FROM league_points_adjustment
            WHERE season_id = :season_id
            GROUP BY team_id
          ) adj ON adj.team_id = b.team_id
        )
        SELECT ROW_NUMBER() OVER (ORDER BY pts DESC, gd DESC, gf DESC, name ASC)::INT AS position,
               team_id, name,
               pld, w, d, l, gf, ga, gd, pts
        FROM adjusted
        ORDER BY position ASC;
    """)
    params = {"season_id": season_id, "win_pts": win_pts, "draw_pts": draw_pts, "loss_pts": loss_pts}
    if up_to_matchday is not None:
        params["md"] = up_to_matchday
    return db.execute(sql, params).mappings().all()

