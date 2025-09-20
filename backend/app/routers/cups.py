import re
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from ..db import get_db
from ..core.templates import templates
from ..models import Season, Stage, StageRound, StageGroup, Team  # (Fixture model import not required)

router = APIRouter(
    prefix="/competitions/{comp_id}/seasons/{season_id}/cup",
    tags=["cup"],
)

# -- helper: find the "groups" stage if present --
def _get_stage_of_format(db: Session, season_id: int, fmt: str):
    return (
        db.execute(
            select(Stage)
            .where(Stage.season_id == season_id, Stage.format.ilike(fmt))
            .order_by(Stage.stage_order.asc())
        )
        .scalars()
        .first()
    )

# ---------------------------
# Overview
# ---------------------------

@router.get("/overview", response_class=HTMLResponse)
def cup_overview(
    comp_id: int,
    season_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    # validate season
    season = db.execute(
        select(Season).where(
            Season.season_id == season_id, Season.competition_id == comp_id
        )
    ).scalar_one_or_none()
    if not season:
        raise HTTPException(404, "Season not found for this competition")

    stages = (
    db.execute(
        select(Stage)
        .where(Stage.season_id == season_id)
        .order_by(Stage.stage_order.desc())
    )
    .scalars()
    .all()
)

    # build per-stage info
    stage_infos = []
    for s in stages:
        rounds = (
            db.execute(
                select(StageRound)
                .where(StageRound.stage_id == s.stage_id)
                .order_by(StageRound.stage_round_order.asc())
            )
            .scalars()
            .all()
        )
        n_fixtures = db.execute(
            text(
                """
            SELECT COUNT(*)
            FROM fixture
            WHERE stage_round_id IN (
              SELECT stage_round_id FROM stage_round WHERE stage_id = :sid
            )
            """
            ),
            {"sid": s.stage_id},
        ).scalar_one()

        groups = []
        if s.format == "groups":
            groups = (
                db.execute(
                    select(StageGroup)
                    .where(StageGroup.stage_id == s.stage_id)
                    .order_by(StageGroup.code, StageGroup.name)
                )
                .scalars()
                .all()
            )

        stage_infos.append(
            {
                "stage": s,
                "rounds": rounds,
                "groups": groups,
                "n_fixtures": n_fixtures,
            }
        )

    # winner + final (from the latest KO/Play-offs stage with fixtures)
    winner_name = None
    final_fixtures = []

    ko_stage = db.execute(
        text(
            """
        WITH ko AS (
          SELECT s.stage_id, s.stage_order
          FROM stage s
          WHERE s.season_id = :season_id
            AND s.format IN ('knockout','playoffs')
        ),
        agg AS (
          SELECT k.stage_id,
                 COUNT(DISTINCT r.stage_round_id) AS n_rounds,
                 COUNT(f.fixture_id)              AS n_fixtures,
                 MAX(s.stage_order)               AS stage_order
          FROM ko k
          LEFT JOIN stage s       ON s.stage_id = k.stage_id
          LEFT JOIN stage_round r ON r.stage_id = k.stage_id
          LEFT JOIN fixture f     ON f.stage_round_id = r.stage_round_id
          GROUP BY k.stage_id
        )
        SELECT stage_id
        FROM agg
        WHERE n_rounds > 0 AND n_fixtures > 0
        ORDER BY stage_order DESC
        LIMIT 1
        """
        ),
        {"season_id": season_id},
    ).scalar_one_or_none()

    if ko_stage:
        final_round = (
            db.execute(
                select(StageRound)
                .where(StageRound.stage_id == ko_stage)
                .order_by(StageRound.stage_round_order.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if final_round:
            final_fixtures = db.execute(
                text(
                    """
                SELECT f.fixture_id, f.kickoff_utc, f.fixture_status,
                       f.ft_home_score, f.ft_away_score,
                       f.et_home_score, f.et_away_score,
                       f.pen_home_score, f.pen_away_score,
                       f.went_to_extra_time, f.went_to_penalties,
                       th.team_id AS home_id, th.name AS home_name,
                       ta.team_id AS away_id, ta.name AS away_name
                FROM fixture f
                JOIN team th ON th.team_id = f.home_team_id
                JOIN team ta ON ta.team_id = f.away_team_id
                WHERE f.stage_round_id = :rid
                ORDER BY f.kickoff_utc, f.fixture_id
                """
                ),
                {"rid": final_round.stage_round_id},
            ).mappings().all()

            # determine winner (2 legs: sum FT; 1 leg: FT/ET/Pens)
            if len(final_fixtures) == 2:
                leg1, leg2 = final_fixtures[0], final_fixtures[1]
                A_id, A_name = leg1["home_id"], leg1["home_name"]
                B_id, B_name = leg1["away_id"], leg1["away_name"]
                A_goals = (leg1["ft_home_score"] or 0) + (leg2["ft_away_score"] or 0)
                B_goals = (leg1["ft_away_score"] or 0) + (leg2["ft_home_score"] or 0)
                if A_goals > B_goals:
                    winner_name = A_name
                elif B_goals > A_goals:
                    winner_name = B_name
                elif leg2["went_to_penalties"]:
                    winner_name = (
                        A_name
                        if (leg2["pen_home_score"] or 0)
                        > (leg2["pen_away_score"] or 0)
                        else B_name
                    )
            elif len(final_fixtures) == 1:
                f = final_fixtures[0]
                if f["ft_home_score"] is not None and f["ft_away_score"] is not None:
                    if f["ft_home_score"] > f["ft_away_score"]:
                        winner_name = f["home_name"]
                    elif f["ft_away_score"] > f["ft_home_score"]:
                        winner_name = f["away_name"]
                    elif f["went_to_penalties"]:
                        winner_name = (
                            f["home_name"]
                            if (f["pen_home_score"] or 0)
                            > (f["pen_away_score"] or 0)
                            else f["away_name"]
                        )

    return templates.TemplateResponse(
        "cup_overview.html",
        {
            "request": request,
            "competition_id": comp_id,
            "season_id": season_id,
            "stage_infos": stage_infos,
            "winner_name": winner_name,
            "final_fixtures": final_fixtures,
        },
    )

# ---------------------------
# Groups
# ---------------------------

@router.get("/groups", response_class=HTMLResponse)
def cup_groups_index(
    comp_id: int, season_id: int, request: Request, stage_id: int | None = Query(None), db: Session = Depends(get_db)
):
    if stage_id:
        groups_stage = db.execute(select(Stage).where(Stage.stage_id == stage_id)).scalar_one_or_none()
    else:
        groups_stage = _get_stage_of_format(db, season_id, "groups")
    
    if not groups_stage:
        raise HTTPException(404, "No group stage for this season")
    groups = (
        db.execute(
            select(StageGroup)
            .where(StageGroup.stage_id == groups_stage.stage_id)
            .order_by(StageGroup.code, StageGroup.name)
        )
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        "cup_groups.html",
        {
            "request": request,
            "competition_id": comp_id,
            "season_id": season_id,
            "stage": groups_stage,
            "groups": groups,
        },
    )

@router.get("/group/{group_id}", response_class=HTMLResponse)
def cup_group_table(
    comp_id: int,
    season_id: int,
    group_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    grp = db.execute(select(StageGroup).where(StageGroup.group_id == group_id)).scalar_one_or_none()
    if not grp:
        raise HTTPException(404, "Group not found")
    stage = db.execute(select(Stage).where(Stage.stage_id == grp.stage_id)).scalar_one()
    if stage.season_id != season_id:
        raise HTTPException(404, "Group does not belong to this season")

    # --- 1) Try snapshot
    has_snapshot = db.execute(text("""
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
          WHERE table_name = 'group_table_snapshot'
        )
    """)).scalar_one()

    table_is_snapshot = False
    table_rows = []

    adj_count = db.execute(text("""
            SELECT COUNT(*) FROM group_points_adjustment WHERE group_id = :gid
        """), {"gid": group_id}).scalar_one()

    if has_snapshot:
        table_rows = db.execute(text("""
            SELECT gts.position,
                   t.name,
                   gts.played, gts.wins, gts.draws, gts.losses,
                   gts.goals_for AS gf, gts.goals_against AS ga,
                   gts.goal_diff AS gd, gts.points AS pts,
                   gts.notes
            FROM group_table_snapshot gts
            JOIN team t ON t.team_id = gts.team_id
            WHERE gts.group_id = :gid
            ORDER BY gts.position ASC, t.name ASC
        """), {"gid": group_id}).mappings().all()

        if table_rows:
            table_is_snapshot = True

    # --- 2) Else compute live (3-1-0) + group_points_adjustment
    if not table_rows:
        # (Optional) if you want to respect season_points_rule, fetch it here and parameterize win/draw/loss points.
        win_pts, draw_pts, loss_pts = 3, 1, 0

        sql = text(f"""
            WITH gfix AS (
              SELECT f.*
              FROM fixture f
              WHERE f.group_id = :gid
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
              FROM gfix GROUP BY home_team_id
            ),
            away AS (
              SELECT away_team_id AS team_id,
                     COUNT(*) AS pld,
                     SUM(CASE WHEN ft_away_score > ft_home_score THEN 1 ELSE 0 END) AS w,
                     SUM(CASE WHEN ft_away_score = ft_home_score THEN 1 ELSE 0 END) AS d,
                     SUM(CASE WHEN ft_away_score < ft_home_score THEN 1 ELSE 0 END) AS l,
                     SUM(ft_away_score) AS gf,
                     SUM(ft_home_score) AS ga
              FROM gfix GROUP BY away_team_id
            ),
            agg AS (
              SELECT COALESCE(h.team_id, a.team_id) AS team_id,
                     COALESCE(h.pld,0) + COALESCE(a.pld,0) AS pld,
                     COALESCE(h.w,0)   + COALESCE(a.w,0)   AS w,
                     COALESCE(h.d,0)   + COALESCE(a.d,0)   AS d,
                     COALESCE(h.l,0)   + COALESCE(a.l,0)   AS l,
                     COALESCE(h.gf,0)  + COALESCE(a.gf,0)  AS gf,
                     COALESCE(h.ga,0)  + COALESCE(a.ga,0)  AS ga
              FROM home h FULL OUTER JOIN away a ON a.team_id = h.team_id
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
                FROM group_points_adjustment
                WHERE group_id = :gid
                GROUP BY team_id
              ) adj ON adj.team_id = b.team_id
            )
            SELECT ROW_NUMBER() OVER (ORDER BY pts DESC, gd DESC, gf DESC, name ASC)::INT AS position,
                   team_id, name,
                   pld AS played, w AS wins, d AS draws, l AS losses,
                   gf, ga, gd, pts
            FROM adjusted
            ORDER BY position ASC;
        """)
        table_rows = db.execute(sql, {"gid": group_id, "win_pts": win_pts, "draw_pts": draw_pts, "loss_pts": loss_pts}).mappings().all()

    # fixtures (unchanged)
    fixtures = db.execute(text("""
        SELECT f.fixture_id, f.kickoff_utc, f.fixture_status,
               f.ft_home_score, f.ft_away_score,
               th.name AS home_name, ta.name AS away_name
        FROM fixture f
        JOIN team th ON th.team_id = f.home_team_id
        JOIN team ta ON ta.team_id = f.away_team_id
        WHERE f.group_id = :gid
        ORDER BY f.kickoff_utc, f.fixture_id
    """), {"gid": group_id}).mappings().all()

    return templates.TemplateResponse(
        "cup_group.html",
        {
            "request": request,
            "competition_id": comp_id,
            "season_id": season_id,
            "stage": stage,
            "group": grp,
            "table": table_rows,
            "table_is_snapshot": table_is_snapshot,
            "adjustments_applied": adj_count > 0,
            "fixtures": fixtures,
        },
    )

# ---------------------------
# Bracket (columnar / tree-ish)
# ---------------------------

@router.get("/bracket", response_class=HTMLResponse)
def cup_bracket(
    comp_id: int,
    season_id: int,
    request: Request,
    stage_id: int | None = Query(default=None),  # allow selecting a specific KO/playoffs stage
    db: Session = Depends(get_db),
):
    # choose stage: explicit ?stage_id= or latest KO/Play-offs stage with fixtures
    if stage_id is None:
        ko_stage = db.execute(
            text(
                """
            WITH ko AS (
              SELECT s.stage_id, s.stage_order
              FROM stage s
              WHERE s.season_id = :season_id
                AND s.format IN ('knockout','playoffs')
            ),
            agg AS (
              SELECT k.stage_id,
                     COUNT(DISTINCT r.stage_round_id) AS n_rounds,
                     COUNT(f.fixture_id)              AS n_fixtures,
                     MAX(s.stage_order)               AS stage_order
              FROM ko k
              LEFT JOIN stage s       ON s.stage_id = k.stage_id
              LEFT JOIN stage_round r ON r.stage_id = k.stage_id
              LEFT JOIN fixture f     ON f.stage_round_id = r.stage_round_id
              GROUP BY k.stage_id
            )
            SELECT stage_id
            FROM agg
            WHERE n_rounds > 0 AND n_fixtures > 0
            ORDER BY stage_order DESC
            LIMIT 1
            """
            ),
            {"season_id": season_id},
        ).scalar_one_or_none()

        if not ko_stage:
            raise HTTPException(404, "No knockout stage with fixtures found for this season")
        stage_id = int(ko_stage)

    ko_stage = db.execute(select(Stage).where(Stage.stage_id == stage_id)).scalar_one_or_none()
    if not ko_stage or ko_stage.season_id != season_id:
        raise HTTPException(404, "Knockout stage not found for this season")

    rounds = (
        db.execute(
            select(StageRound)
            .where(StageRound.stage_id == ko_stage.stage_id)
            .order_by(StageRound.stage_round_order.asc())
        )
        .scalars()
        .all()
    )

    # columnar ties per round
    round_cols: list[list[dict]] = []

    for rnd in rounds:
        rows = db.execute(
            text(
                """
            SELECT f.fixture_id, f.kickoff_utc, f.fixture_status,
                   f.ft_home_score, f.ft_away_score,
                   f.et_home_score, f.et_away_score,
                   f.pen_home_score, f.pen_away_score,
                   f.went_to_extra_time, f.went_to_penalties,
                   th.team_id AS home_id, th.name AS home_name,
                   ta.team_id AS away_id, ta.name AS away_name
            FROM fixture f
            JOIN team th ON th.team_id = f.home_team_id
            JOIN team ta ON ta.team_id = f.away_team_id
            WHERE f.stage_round_id = :rid
            ORDER BY f.kickoff_utc, f.fixture_id
            """
            ),
            {"rid": rnd.stage_round_id},
        ).mappings().all()

        # group legs into ties by canonical pair
        ties: dict[tuple[int, int], dict] = {}
        for r in rows:
            a_id, a_name = r["home_id"], r["home_name"]
            b_id, b_name = r["away_id"], r["away_name"]
            key = (min(a_id, b_id), max(a_id, b_id))
            if key not in ties:
                ties[key] = {
                    "a_id": key[0],
                    "b_id": key[1],
                    "a_name": a_name if a_id == key[0] else b_name,
                    "b_name": b_name if b_id == key[1] else a_name,
                    "legs": [],
                }
            ties[key]["legs"].append(r)

        column: list[dict] = []
        for _, t in ties.items():
            a_goals = b_goals = 0
            went_et = False
            pens_note = ""
            last_leg = None
            for leg in t["legs"]:
                last_leg = leg
                if leg["home_id"] == t["a_id"]:
                    a_goals += (leg["ft_home_score"] or 0)
                    b_goals += (leg["ft_away_score"] or 0)
                else:
                    a_goals += (leg["ft_away_score"] or 0)
                    b_goals += (leg["ft_home_score"] or 0)
                went_et = went_et or bool(leg["went_to_extra_time"])
                if leg["went_to_penalties"]:
                    pens_note = f" (Pens {leg['pen_home_score']}–{leg['pen_away_score']})"

            winner = None
            if a_goals > b_goals:
                winner = t["a_name"]
            elif b_goals > a_goals:
                winner = t["b_name"]
            elif last_leg and last_leg["went_to_penalties"]:
                if last_leg["home_id"] == t["a_id"]:
                    winner = (
                        t["a_name"]
                        if (last_leg["pen_home_score"] or 0)
                        > (last_leg["pen_away_score"] or 0)
                        else t["b_name"]
                    )
                else:
                    winner = (
                        t["a_name"]
                        if (last_leg["pen_away_score"] or 0)
                        > (last_leg["pen_home_score"] or 0)
                        else t["b_name"]
                    )

            column.append(
                {
                    "round_id": rnd.stage_round_id,
                    "round_name": rnd.name,
                    "a_name": t["a_name"],
                    "b_name": t["b_name"],
                    "legs": t["legs"],
                    "agg": f"{a_goals}–{b_goals}",
                    "et": went_et,
                    "pens": pens_note,
                    "winner": winner,
                }
            )

        round_cols.append(column)

    LEG1_RE = re.compile(r'\b(?:1st|first|leg\s*1)\b', re.I)
    LEG2_RE = re.compile(r'\b(?:2nd|2st|second|leg\s*2)\b', re.I)  # NOTE: handles "2st"
    FINAL_RE = re.compile(r'\bfinal\b', re.I)

    def _is_leg1(name: str) -> bool:
        return bool(LEG1_RE.search(name or ""))

    def _is_leg2(name: str) -> bool:
        return bool(LEG2_RE.search(name or ""))

    def _is_final_single(name: str) -> bool:
        n = name or ""
        return bool(FINAL_RE.search(n)) and not _is_leg1(n) and not _is_leg2(n)

    def _pair_key(a_name: str, b_name: str):
        return tuple(sorted([a_name, b_name]))

    # 1) Mark types on each round and build a previous-round map for pairing
    for i, rnd in enumerate(rounds):
        rname = rnd.name or ""
        is1 = _is_leg1(rname)
        is2 = _is_leg2(rname)
        is_single_final = _is_final_single(rname)

        col = round_cols[i] if i < len(round_cols) else []
        for tie in col:
            tie["__is_leg1"] = is1
            tie["__is_leg2"] = is2
            tie["__is_single_final"] = is_single_final
            tie["combined_agg"] = None
            tie["combined_agg_leg2_home"] = None
            tie["combined_winner"] = None

        # 2) If this is a 2nd-leg round, compute combined aggregates with previous round
        if is2 and i > 0:
            prev_col = round_cols[i - 1] or []
            prev_map = { _pair_key(t["a_name"], t["b_name"]): t for t in prev_col }

            for tie in col:
                key = _pair_key(tie["a_name"], tie["b_name"])
                t1 = prev_map.get(key)
                legs = []
                if t1:
                    legs.extend(t1["legs"])
                legs.extend(tie.get("legs", []))

                # recompute across both legs from A/B of the *current* tie
                a_goals = b_goals = 0
                went_et = False
                pens_note = ""
                last_leg = None
                for leg in legs:
                    last_leg = leg
                    if leg["home_name"] == tie["a_name"]:
                        a_goals += (leg["ft_home_score"] or 0)
                        b_goals += (leg["ft_away_score"] or 0)
                    elif leg["away_name"] == tie["a_name"]:
                        a_goals += (leg["ft_away_score"] or 0)
                        b_goals += (leg["ft_home_score"] or 0)
                    went_et = went_et or bool(leg["went_to_extra_time"])
                    if leg["went_to_penalties"]:
                        pens_note = f" (Pens {leg['pen_home_score']}–{leg['pen_away_score']})"

                # winner across both legs
                comb_winner = None
                if a_goals > b_goals:
                    comb_winner = tie["a_name"]
                elif b_goals > a_goals:
                    comb_winner = tie["b_name"]
                elif last_leg and last_leg["went_to_penalties"]:
                    if last_leg["home_name"] == tie["a_name"]:
                        comb_winner = tie["a_name"] if (last_leg["pen_home_score"] or 0) > (last_leg["pen_away_score"] or 0) else tie["b_name"]
                    else:
                        comb_winner = tie["a_name"] if (last_leg["pen_away_score"] or 0) > (last_leg["pen_home_score"] or 0) else tie["b_name"]

                # combined aggregate texts
                agg_text = f"{a_goals}–{b_goals}" + (" (ET)" if went_et else "") + pens_note
                # 2nd-leg home orientation
                leg2 = tie["legs"][0] if tie.get("legs") else None
                if leg2:
                    if leg2["home_name"] == tie["a_name"]:
                        agg_text_leg2_home = agg_text
                    else:
                        agg_text_leg2_home = f"{b_goals}–{a_goals}" + (" (ET)" if went_et else "") + pens_note
                else:
                    agg_text_leg2_home = agg_text

                tie["combined_agg"] = agg_text
                tie["combined_agg_leg2_home"] = agg_text_leg2_home
                tie["combined_winner"] = comb_winner

    # ---- Build paired blocks for mini-table view (combine 1st+2nd legs) ----
    paired_blocks = []  # list of {"title": "...", "pairs": [ {leg1, leg2_or_None, winner, agg_text} ]}

    def _pair_key(t):
        # canonical key by team names (works with home/away swapped)
        return frozenset((t["a_name"], t["b_name"]))

    i = 0
    while i < len(rounds):
        rnd = rounds[i]
        col = round_cols[i]

        # Heuristic: if this round looks like "1st Leg" and there is a following round that looks like "2"
        # we pair i with i+1; else it's a single-leg round (finals, one-off ties).
        name_lower = (rnd.name or "").lower()
        has_next = i + 1 < len(rounds)
        next_looks_like_leg2 = False
        if has_next:
            nxt = rounds[i + 1]
            nl = (nxt.name or "").lower()
            next_looks_like_leg2 = ("2" in nl) or ("second" in nl) or ("2nd" in nl)

        if ("1" in name_lower or "first" in name_lower or "1st" in name_lower) and has_next and next_looks_like_leg2:
            # Pair column i and i+1 by team set
            next_col = round_cols[i + 1]
            next_map = { _pair_key(t): t for t in next_col }

            pairs = []
            for t in col:
                key = _pair_key(t)
                t2 = next_map.get(key)
                # Build aggregate text from tie already computed in col (t) if winner/agg there reflects both legs
                # Our earlier aggregate was per round; recompute across both legs here for safety.
                legs = list(t["legs"])
                if t2:
                    legs += list(t2["legs"])

                # recompute agg across both legs from canonical A vs B
                a_goals = b_goals = 0
                went_et = False
                pens_note = ""
                last_leg = None
                for leg in legs:
                    last_leg = leg
                    if leg["home_name"] == t["a_name"]:
                        a_goals += (leg["ft_home_score"] or 0)
                        b_goals += (leg["ft_away_score"] or 0)
                    elif leg["away_name"] == t["a_name"]:
                        a_goals += (leg["ft_away_score"] or 0)
                        b_goals += (leg["ft_home_score"] or 0)
                    else:
                        # Shouldn't happen if names are consistent
                        pass
                    went_et = went_et or bool(leg["went_to_extra_time"])
                    if leg["went_to_penalties"]:
                        pens_note = f" (Pens {leg['pen_home_score']}–{leg['pen_away_score']})"

                winner = None
                if a_goals > b_goals:
                    winner = t["a_name"]
                elif b_goals > a_goals:
                    winner = t["b_name"]
                elif last_leg and last_leg["went_to_penalties"]:
                    # decide from last leg’s perspective
                    if last_leg["home_name"] == t["a_name"]:
                        winner = t["a_name"] if (last_leg["pen_home_score"] or 0) > (last_leg["pen_away_score"] or 0) else t["b_name"]
                    else:
                        winner = t["a_name"] if (last_leg["pen_away_score"] or 0) > (last_leg["pen_home_score"] or 0) else t["b_name"]

                # Build default A–B aggregate text
                agg_text = f"{a_goals}–{b_goals}" + (" (ET)" if went_et else "") + pens_note

                # If we have a second leg, build aggregate from the perspective of the 2nd-leg home team
                agg_text_leg2_home = None
                leg2_obj = t2["legs"][0] if (t2 and t2["legs"]) else None
                if leg2_obj:
                    if leg2_obj["home_name"] == t["a_name"]:
                        agg_text_leg2_home = agg_text  # A is home in leg 2 → keep A–B order
                    else:
                        # flip to B–A order
                        agg_text_leg2_home = f"{b_goals}–{a_goals}" + (" (ET)" if went_et else "") + pens_note

                pairs.append({
                    "title": f"{rnd.name} — Pair {len(pairs)+1}",
                    "a_name": t["a_name"],
                    "b_name": t["b_name"],
                    "leg1": t["legs"][0] if t["legs"] else None,
                    "leg2": (t2["legs"][0] if (t2 and t2["legs"]) else None),
                    "winner": winner,
                    "agg_text": agg_text,                         # A–B orientation
                    "agg_text_leg2_home": agg_text_leg2_home,     # 2nd-leg home–away orientation
                })

            paired_blocks.append({
                "round_title": rnd.name.replace("1st Leg", "").replace("First Leg", "").strip() or rnd.name,
                "first_round_name": rnd.name,                 # <— add
                "second_round_name": rounds[i + 1].name,      # <— add
                "pairs": pairs,
            })
            i += 2 # skip the next round; already paired
        else:
            # Single-leg round (e.g., Final) or no matching 2nd leg
            pairs = []
            for t in col:
                # compute single-leg aggregate just from its legs (usually 1)
                a_goals = b_goals = 0
                went_et = False
                pens_note = ""
                last_leg = None
                for leg in t["legs"]:
                    last_leg = leg
                    if leg["home_name"] == t["a_name"]:
                        a_goals += (leg["ft_home_score"] or 0)
                        b_goals += (leg["ft_away_score"] or 0)
                    elif leg["away_name"] == t["a_name"]:
                        a_goals += (leg["ft_away_score"] or 0)
                        b_goals += (leg["ft_home_score"] or 0)
                    went_et = went_et or bool(leg["went_to_extra_time"])
                    if leg["went_to_penalties"]:
                        pens_note = f" (Pens {leg['pen_home_score']}–{leg['pen_away_score']})"

                winner = t.get("winner")
                pairs.append({
                    "title": f"{rnd.name} — Pair {len(pairs)+1}",
                    "a_name": t["a_name"],
                    "b_name": t["b_name"],
                    "leg1": t["legs"][0] if t["legs"] else None,
                    "leg2": None,
                    "winner": winner,
                    "agg_text": f"{a_goals}–{b_goals}" + ( " (ET)" if went_et else "" ) + pens_note,
                })

            paired_blocks.append({
                "round_title": rnd.name,
                "first_round_name": rnd.name,     # <— add
                "second_round_name": None,        # <— add
                "pairs": pairs,
            })
            i += 1


    return templates.TemplateResponse(
        "cup_bracket.html",
        {
            "request": request,
            "competition_id": comp_id,
            "season_id": season_id,
            "stage": ko_stage,
            "rounds": rounds,
            "round_cols": round_cols,
            "paired_blocks": paired_blocks,
        },
    )
