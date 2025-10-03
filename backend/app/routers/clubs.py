from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..db import get_db
from ..models import Club, Country, Stadium
from ..schemas import ClubCreate, ClubRead
from ..core.templates import templates

router = APIRouter(prefix="/clubs", tags=["clubs"])

@router.get("", response_class=HTMLResponse)
def clubs_page(
    request: Request,
    q: str | None = None,
    country_id: int | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Club)
    if q:
        stmt = stmt.where(Club.name.ilike(f"%{q.strip()}%"))
    if country_id:
        stmt = stmt.where(Club.country_id == country_id)
    rows = db.execute(stmt.order_by(Club.name)).scalars().all()

    countries = db.execute(select(Country.country_id, Country.name).order_by(Country.name)).all()
    country_map = {cid: cname for cid, cname in countries}

    return templates.TemplateResponse(
        "clubs.html",
        {"request": request, "clubs": rows, "q": q or "", "country_id": country_id, "country_map": country_map},
    )


@router.get("/{club_id}", response_class=HTMLResponse)
def club_detail_page(club_id: int, request: Request, db: Session = Depends(get_db)):
    club = db.execute(select(Club).where(Club.club_id == club_id)).scalar_one_or_none()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    country = None
    stadium = None
    if club.country_id:
        country = db.execute(select(Country).where(Country.country_id == club.country_id)).scalar_one_or_none()
    if club.stadium_id:
        stadium = db.execute(select(Stadium).where(Stadium.stadium_id == club.stadium_id)).scalar_one_or_none()
    return templates.TemplateResponse(
        "club_detail.html",
        {"request": request, "club": club, "country": country, "stadium": stadium}
    )


@router.get("/api", response_model=list[ClubRead])
def list_clubs(country_id: int | None = None, limit: int = 200, db: Session = Depends(get_db)):
    stmt = select(Club)
    if country_id:
        stmt = stmt.where(Club.country_id == country_id)
    rows = db.execute(stmt.order_by(Club.name).limit(limit)).scalars().all()
    return [ClubRead.model_validate(r) for r in rows]


@router.post("/api", response_model=ClubRead)
def create_club(payload: ClubCreate, db: Session = Depends(get_db)):
    exists = db.execute(select(Club).where(Club.name.ilike(payload.name.strip()))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="Club already exists")

    row = Club(
        name=payload.name.strip(),
        short_name=(payload.short_name or None),
        founded=payload.founded,
        country_id=payload.country_id,
        stadium_id=payload.stadium_id,
        colors=(payload.colors or None),
        logo_filename=payload.logo_filename,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ClubRead.model_validate(row, from_attributes=True)
