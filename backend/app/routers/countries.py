# backend/app/routers/countries.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..db import get_db
from ..models import Country, Association
from ..schemas import CountryCreate, CountryRead
from ..core.templates import templates

router = APIRouter(prefix="/countries", tags=["countries"])

@router.get("", response_class=HTMLResponse)
def countries_page(request: Request, q: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Country)
    if q:
        q_like = f"%{q.strip()}%"
        stmt = stmt.where(Country.name.ilike(q_like))
    rows = db.execute(stmt.order_by(Country.name)).scalars().all()
    ass_ids = {c.confed_ass_id for c in rows if c.confed_ass_id}
    ass_map = {}
    if ass_ids:
        assocs = db.execute(select(Association).where(Association.ass_id.in_(ass_ids))).scalars().all()
        ass_map = {a.ass_id: a for a in assocs}
    return templates.TemplateResponse(
        "countries.html",
        {"request": request, "countries": rows, "q": q or "", "ass_map": ass_map},
    )

@router.get("/{country_id}", response_class=HTMLResponse)
def country_detail_page(country_id: int, request: Request, db: Session = Depends(get_db)):
    country = db.execute(select(Country).where(Country.country_id == country_id)).scalar_one_or_none()
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")
    association = None
    if country.confed_ass_id:
        association = db.execute(
            select(Association).where(Association.ass_id == country.confed_ass_id)
        ).scalar_one_or_none()
    return templates.TemplateResponse(
        "country_detail.html",
        {"request": request, "country": country, "association": association},
    )

@router.get("/api", response_model=list[CountryRead])
def list_countries(db: Session = Depends(get_db)):
    rows = db.execute(select(Country).order_by(Country.name)).scalars().all()
    return [CountryRead(country_id=r.country_id, name=r.name, fifa_code=r.fifa_code) for r in rows]

@router.post("/api", response_model=CountryRead)
def create_country(payload: CountryCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    fifa_code = payload.fifa_code.upper() if payload.fifa_code else None
    exists = db.execute(select(Country).where(Country.name.ilike(name))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="Country already exists")
    row = Country(name=name, fifa_code=fifa_code)
    db.add(row)
    db.commit()
    db.refresh(row)
    return CountryRead(country_id=row.country_id, name=row.name, fifa_code=row.fifa_code)