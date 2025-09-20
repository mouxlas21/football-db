# backend/app/routers/competitions.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..db import get_db
from ..models import Competition, Country, Association, Season
from ..schemas import CompetitionCreate, CompetitionRead
from ..core.templates import templates

router = APIRouter(prefix="/competitions", tags=["competitions"])

@router.get("", response_class=HTMLResponse)
def competitions_page(request: Request, q: str | None = None, type: str | None = None, country_id: int | None = None, organizer_ass_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(Competition)
    if q:
        stmt = stmt.where(Competition.name.ilike(f"%{q.strip()}%"))
    if type:
        stmt = stmt.where(Competition.type.ilike(type.strip()))
    if country_id:
        stmt = stmt.where(Competition.country_id == country_id)
    if organizer_ass_id:
        stmt = stmt.where(Competition.organizer_ass_id == organizer_ass_id)

    rows = db.execute(stmt.order_by(Competition.name)).scalars().all()

    countries = db.execute(select(Country.country_id, Country.name).order_by(Country.name)).all()
    country_map = {cid: cname for cid, cname in countries}
    ass_ids = {cmp.organizer_ass_id for cmp in rows if cmp.organizer_ass_id}
    ass_map = {}
    if ass_ids:
        assocs = db.execute(select(Association).where(Association.ass_id.in_(ass_ids))).scalars().all()
        ass_map = {a.ass_id: a for a in assocs}

    return templates.TemplateResponse(
        "competitions.html",
        {
            "request": request,
            "competitions": rows,
            "q": q or "",
            "type": type or "",
            "country_id": country_id,
            "country_map": country_map,
            "ass_map": ass_map,
        },
    )

@router.get("/{competition_id}", response_class=HTMLResponse)
def competition_detail_page(competition_id: int, request: Request, db: Session = Depends(get_db)):
    comp = db.execute(select(Competition).where(Competition.competition_id == competition_id)).scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Competition not found")

    country = db.execute(select(Country).where(Country.country_id == comp.country_id)).scalar_one_or_none() if comp.country_id else None
    organizer = db.execute(select(Association).where(Association.ass_id == comp.organizer_ass_id)).scalar_one_or_none() if comp.organizer_ass_id else None

    # seasons for this competition
    from ..models import Season
    seasons = db.execute(select(Season).where(Season.competition_id == comp.competition_id).order_by(Season.start_date.desc().nullslast(), Season.name.desc())).scalars().all()

    return templates.TemplateResponse(
        "competition_detail.html",
        {"request": request, "competition": comp, "country": country, "organizer": organizer, "seasons": seasons},
    )

@router.get("/{competition_id}/seasons/{season_id}")
def season_overview_redirect(competition_id: int, season_id: int, db: Session = Depends(get_db)):
    # verify season belongs to competition
    season = db.execute(
        select(Season).where(Season.season_id == season_id, Season.competition_id == competition_id)
    ).scalar_one_or_none()
    if not season:
        raise HTTPException(status_code=404, detail="Season not found for this competition")

    comp = db.execute(
        select(Competition).where(Competition.competition_id == competition_id)
    ).scalar_one()

    # redirect to the correct overview per competition type
    if comp.type == "league":
        return RedirectResponse(
            url=f"/competitions/{competition_id}/seasons/{season_id}/league/overview",
            status_code=307,
        )
    elif comp.type == "cup":
        return RedirectResponse(
            url=f"/competitions/{competition_id}/seasons/{season_id}/cup/overview",
            status_code=307,
        )
    else:
        # fallback: send to league for now, or render a generic season page if you prefer
        return RedirectResponse(
            url=f"/competitions/{competition_id}/seasons/{season_id}/league/overview",
            status_code=307,
        )

# --- JSON API ---

@router.get("/api", response_model=list[CompetitionRead])
def api_list_competitions(
    type: str | None = None,
    country_id: int | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    stmt = select(Competition)
    if type:
        stmt = stmt.where(Competition.type.ilike(type.strip()))
    if country_id:
        stmt = stmt.where(Competition.country_id == country_id)
    rows = db.execute(stmt.order_by(Competition.name).limit(limit)).scalars().all()
    return [CompetitionRead.model_validate(r, from_attributes=True) for r in rows]

@router.get("/api/{competition_id}", response_model=CompetitionRead)
def api_get_competition(competition_id: int, db: Session = Depends(get_db)):
    row = db.execute(select(Competition).where(Competition.competition_id == competition_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Competition not found")
    return CompetitionRead.model_validate(row, from_attributes=True)

@router.post("/api", response_model=CompetitionRead)
def api_create_competition(payload: CompetitionCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    exists = db.execute(select(Competition).where(Competition.name.ilike(name))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="Competition already exists")

    organizer_ass_id = None
    if payload.organizer_code:
        assoc = db.execute(select(Association).where(Association.code.ilike(payload.organizer_code.strip()))).scalar_one_or_none()
        if not assoc:
            raise HTTPException(status_code=400, detail="Organizer association code not found")
        organizer_ass_id = assoc.ass_id

    row = Competition(
        name=name,
        type=payload.type,
        country_id=payload.country_id,
        organizer_ass_id=organizer_ass_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return CompetitionRead.model_validate(row, from_attributes=True)
