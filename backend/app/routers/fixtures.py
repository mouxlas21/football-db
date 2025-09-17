# backend/app/routers/fixtures.py
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from ..db import get_db
from ..models import Fixture, Team, Stadium
from ..core.templates import templates

router = APIRouter(prefix="/fixtures", tags=["fixtures"])

@router.get("", response_class=HTMLResponse)
def fixtures_page(
    request: Request,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    team_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(Fixture).order_by(Fixture.kickoff_utc.desc()).limit(limit)

    conds = []
    if date_from:
        conds.append(Fixture.kickoff_utc >= datetime.combine(date_from, datetime.min.time()).astimezone())
    if date_to:
        end_dt = datetime.combine(date_to, datetime.max.time()).astimezone()
        conds.append(Fixture.kickoff_utc <= end_dt)
    if team_id:
        conds.append((Fixture.home_team_id == team_id) | (Fixture.away_team_id == team_id))

    if conds:
        stmt = select(Fixture).where(and_(*conds)).order_by(Fixture.kickoff_utc.desc()).limit(limit)

    rows = db.execute(stmt).scalars().all()

    # bulk fetch
    team_ids, stad_ids = set(), set()
    for f in rows:
        team_ids.update([f.home_team_id, f.away_team_id])
        if f.winner_team_id:
            team_ids.add(f.winner_team_id)
        if f.stadium_id:
            stad_ids.add(f.stadium_id)

    teams_map = {}
    if team_ids:
        teams = db.execute(select(Team).where(Team.team_id.in_(list(team_ids)))).scalars().all()
        teams_map = {t.team_id: t for t in teams}

    stadiums_map = {}
    if stad_ids:
        stadia = db.execute(select(Stadium).where(Stadium.stadium_id.in_(list(stad_ids)))).scalars().all()
        stadiums_map = {s.stadium_id: s for s in stadia}

    return templates.TemplateResponse(
        "fixtures.html",
        {
            "request": request,
            "fixtures": rows,
            "teams": teams_map,
            "stadiums": stadiums_map,
            "date_from": date_from.isoformat() if date_from else "",
            "date_to": date_to.isoformat() if date_to else "",
            "team_id": team_id,
            "limit": limit,
        },
    )

@router.get("/{fixture_id}", response_class=HTMLResponse)
def fixture_detail_page(fixture_id: int, request: Request, db: Session = Depends(get_db)):
    f = db.execute(select(Fixture).where(Fixture.fixture_id == fixture_id)).scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Fixture not found")
    home = db.execute(select(Team).where(Team.team_id == f.home_team_id)).scalar_one_or_none()
    away = db.execute(select(Team).where(Team.team_id == f.away_team_id)).scalar_one_or_none()
    winner = db.execute(select(Team).where(Team.team_id == f.winner_team_id)).scalar_one_or_none() if f.winner_team_id else None
    stadium = db.execute(select(Stadium).where(Stadium.stadium_id == f.stadium_id)).scalar_one_or_none() if f.stadium_id else None

    return templates.TemplateResponse(
        "fixture_detail.html",
        {"request": request, "f": f, "home": home, "away": away, "winner": winner, "stadium": stadium},
    )
