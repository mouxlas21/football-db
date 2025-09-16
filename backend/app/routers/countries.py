# backend/app/routers/countries.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..db import get_db
from ..models import Country
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
    return templates.TemplateResponse(
        "countries.html",
        {"request": request, "countries": rows, "q": q or ""},
    )

@router.get("/{country_id}", response_class=HTMLResponse)
def country_detail_page(country_id: int, request: Request, db: Session = Depends(get_db)):
    country = db.execute(select(Country).where(Country.country_id == country_id)).scalar_one_or_none()
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")
    return templates.TemplateResponse(
        "country_detail.html",
        {"request": request, "country": country},
    )

@router.get("/api", response_model=list[CountryRead])
def list_countries(db: Session = Depends(get_db)):
    rows = db.execute(select(Country).order_by(Country.name)).scalars().all()
    return [CountryRead(country_id=r.country_id, name=r.name, iso2=r.iso2) for r in rows]

@router.post("/api", response_model=CountryRead)
def create_country(payload: CountryCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    iso2 = payload.iso2.upper() if payload.iso2 else None
    exists = db.execute(select(Country).where(Country.name.ilike(name))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="Country already exists")
    row = Country(name=name, iso2=iso2)
    db.add(row)
    db.commit()
    db.refresh(row)
    return CountryRead(country_id=row.country_id, name=row.name, iso2=row.iso2)