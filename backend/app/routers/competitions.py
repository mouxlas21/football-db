# backend/app/routers/competitions.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..db import get_db
from ..models import Competition, Country
from ..schemas import CompetitionCreate, CompetitionRead
from ..core.templates import templates

router = APIRouter(prefix="/competitions", tags=["competitions"])

@router.get("", response_class=HTMLResponse)
def competitions_page(
    request: Request,
    q: str | None = None,
    type: str | None = None,           # 'league' | 'cup' | etc.
    country_id: int | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Competition)
    if q:
        stmt = stmt.where(Competition.name.ilike(f"%{q.strip()}%"))
    if type:
        stmt = stmt.where(Competition.type.ilike(type.strip()))
    if country_id:
        stmt = stmt.where(Competition.country_id == country_id)

    rows = db.execute(stmt.order_by(Competition.name)).scalars().all()

    countries = db.execute(select(Country.country_id, Country.name).order_by(Country.name)).all()
    country_map = {cid: cname for cid, cname in countries}

    return templates.TemplateResponse(
        "competitions.html",
        {
            "request": request,
            "competitions": rows,
            "q": q or "",
            "type": type or "",
            "country_id": country_id,
            "country_map": country_map,
        },
    )

@router.get("/{competition_id}", response_class=HTMLResponse)
def competition_detail_page(competition_id: int, request: Request, db: Session = Depends(get_db)):
    comp = db.execute(select(Competition).where(Competition.competition_id == competition_id)).scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Competition not found")
    country = None
    if comp.country_id:
        country = db.execute(select(Country).where(Country.country_id == comp.country_id)).scalar_one_or_none()
    return templates.TemplateResponse(
        "competition_detail.html",
        {"request": request, "competition": comp, "country": country},
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
    return [CompetitionRead.from_model(r) for r in rows]

@router.get("/api/{competition_id}", response_model=CompetitionRead)
def api_get_competition(competition_id: int, db: Session = Depends(get_db)):
    row = db.execute(select(Competition).where(Competition.competition_id == competition_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Competition not found")
    return CompetitionRead.from_model(row)

@router.post("/api", response_model=CompetitionRead)
def api_create_competition(payload: CompetitionCreate, db: Session = Depends(get_db)):
    exists = db.execute(select(Competition).where(Competition.name.ilike(payload.name.strip()))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="Competition already exists")
    row = Competition(
        name=payload.name.strip(),
        type=(payload.type or "league"),
        organizer=(payload.organizer or None),
        country_id=payload.country_id,
        confederation=(payload.confederation or None),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return CompetitionRead.from_model(row)