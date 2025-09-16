# backend/app/routers/leagues.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..db import get_db
from ..models import Country, League
from ..schemas import LeagueCreate, LeagueRead
from ..core.templates import templates

router = APIRouter(prefix="/leagues", tags=["leagues"])

# HTML: list
@router.get("", response_class=HTMLResponse)  # /leagues
def leagues_page(request: Request, q: str | None = None, country_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(League)
    if q:
        q_like = f"%{q.strip()}%"
        stmt = stmt.where(League.name.ilike(q_like))
    if country_id:
        stmt = stmt.where(League.country_id == country_id)

    rows = db.execute(stmt.order_by(League.tier.nulls_last(), League.name)).scalars().all()

    countries = db.execute(select(Country.country_id, Country.name)).all()
    country_map = {cid: cname for cid, cname in countries}

    return templates.TemplateResponse(
        "leagues.html",
        {"request": request, "leagues": rows, "q": q or "", "country_id": country_id, "country_map": country_map},
    )

# HTML: detail
@router.get("/{league_id}", response_class=HTMLResponse)
def league_detail_page(league_id: int, request: Request, db: Session = Depends(get_db)):
    league = db.execute(select(League).where(League.league_id == league_id)).scalar_one_or_none()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    country = db.execute(select(Country).where(Country.country_id == league.country_id)).scalar_one_or_none()
    return templates.TemplateResponse("league_detail.html", {"request": request, "league": league, "country": country})

# API: list
@router.get("/api", response_model=list[LeagueRead])  # /leagues/api
def list_leagues(country_id: int | None = None, limit: int = 50, db: Session = Depends(get_db)):
    stmt = select(League)
    if country_id:
        stmt = stmt.where(League.country_id == country_id)
    rows = db.execute(stmt.order_by(League.tier.nulls_last(), League.name).limit(limit)).scalars().all()
    return [LeagueRead.model_validate(r) for r in rows]

# API: get one
@router.get("/api/{league_id}", response_model=LeagueRead)
def get_league(league_id: int, db: Session = Depends(get_db)):
    row = db.execute(select(League).where(League.league_id == league_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="League not found")
    return LeagueRead.model_validate(row)

# API: create
@router.post("/api", response_model=LeagueRead)
def create_league(payload: LeagueCreate, db: Session = Depends(get_db)):
    exists = db.execute(select(League).where(League.name.ilike(payload.name.strip()))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="League already exists")
    row = League(
        name=payload.name.strip(),
        slug=(payload.slug or None),
        tier=payload.tier,
        country_id=payload.country_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return LeagueRead.model_validate(row)
