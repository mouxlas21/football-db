# backend/app/routers/matches.py
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from ..db import get_db
from ..models import Match, Team, Stadium
from ..core.templates import templates

router = APIRouter(prefix="/matches", tags=["matches"])

@router.get("", response_class=HTMLResponse)
def matches_page(
    request: Request,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    team_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(Match).order_by(Match.kickoff_utc.desc()).limit(limit)

    conds = []
    if date_from:
        conds.append(Match.kickoff_utc >= datetime.combine(date_from, datetime.min.time()).astimezone())
    if date_to:
        # include end of day
        end_dt = datetime.combine(date_to, datetime.max.time()).astimezone()
        conds.append(Match.kickoff_utc <= end_dt)
    if team_id:
        conds.append((Match.home_team_id == team_id) | (Match.away_team_id == team_id))

    if conds:
        stmt = select(Match).where(and_(*conds)).order_by(Match.kickoff_utc.desc()).limit(limit)

    rows = db.execute(stmt).scalars().all()

    # fetch teams/stadiums in bulk
    team_ids = set()
    stad_ids = set()
    for m in rows:
        team_ids.add(m.home_team_id)
        team_ids.add(m.away_team_id)
        if m.winner_team_id:
            team_ids.add(m.winner_team_id)
        if m.stadium_id:
            stad_ids.add(m.stadium_id)

    teams_map = {}
    if team_ids:
        teams = db.execute(select(Team).where(Team.team_id.in_(list(team_ids)))).scalars().all()
        teams_map = {t.team_id: t for t in teams}

    stadiums_map = {}
    if stad_ids:
        stadia = db.execute(select(Stadium).where(Stadium.stadium_id.in_(list(stad_ids)))).scalars().all()
        stadiums_map = {s.stadium_id: s for s in stadia}

    return templates.TemplateResponse(
        "matches.html",
        {
            "request": request,
            "matches": rows,
            "teams": teams_map,
            "stadiums": stadiums_map,
            "date_from": date_from.isoformat() if date_from else "",
            "date_to": date_to.isoformat() if date_to else "",
            "team_id": team_id,
            "limit": limit,
        },
    )

@router.get("/{match_id}", response_class=HTMLResponse)
def match_detail_page(match_id: int, request: Request, db: Session = Depends(get_db)):
    m = db.execute(select(Match).where(Match.match_id == match_id)).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Match not found")
    home = db.execute(select(Team).where(Team.team_id == m.home_team_id)).scalar_one_or_none()
    away = db.execute(select(Team).where(Team.team_id == m.away_team_id)).scalar_one_or_none()
    winner = db.execute(select(Team).where(Team.team_id == m.winner_team_id)).scalar_one_or_none() if m.winner_team_id else None
    stadium = db.execute(select(Stadium).where(Stadium.stadium_id == m.stadium_id)).scalar_one_or_none() if m.stadium_id else None

    return templates.TemplateResponse(
        "match_detail.html",
        {"request": request, "m": m, "home": home, "away": away, "winner": winner, "stadium": stadium},
    )