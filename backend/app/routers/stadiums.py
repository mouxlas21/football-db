# app/routers/stadiums.py
from typing import Dict, Any, List
import re, unicodedata

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from ..db import get_db
from ..core.templates import templates
from ..models import Country, Stadium

router = APIRouter(prefix="/stadiums", tags=["Stadiums"])

_slug_re = re.compile(r"[^a-z0-9]+")

def slugify_country(name: str | None) -> str:
    if not name:
        return "unknown"
    # Normalize accents: Türkiye -> Turkıye
    s = unicodedata.normalize("NFKD", name)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = s.replace("&", " ")
    s = _slug_re.sub("-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "unknown"

def _status_clause(status: str):
    status = (status or "active").lower()
    if status == "closed":
        return Stadium.closed_year.is_not(None)
    if status == "all":
        return None
    return Stadium.closed_year.is_(None)

@router.get("", response_class=HTMLResponse, response_model=None)
def stadiums_index(
    request: Request,
    q: str = "",
    status: str = "active",
    db: Session = Depends(get_db),
):
    where = []
    if q:
        ql = f"%{q.lower()}%"
        where = [func.lower(Stadium.name).like(ql) | func.lower(Stadium.city).like(ql)]
    else:
        where = []

    stmt = (
        select(
            Stadium.stadium_id,
            Stadium.name,
            Stadium.city,
            Stadium.capacity,
            Stadium.opened_year,
            Stadium.closed_year,
            Stadium.photo_filename,
            Country.country_id,
            Country.name.label("country_name"),
            Country.flag_filename.label("flag_filename"),
        )
        .join(Country, Country.country_id == Stadium.country_id, isouter=True)
        .order_by(Country.name.nulls_last(), Stadium.name.asc())
    )
    if where:
        stmt = stmt.where(*where)

    rows = db.execute(stmt).all()

    # Buckets by country for active & closed
    active_map: Dict[int | None, Dict[str, Any]] = {}
    closed_map: Dict[int | None, Dict[str, Any]] = {}

    def ensure_bucket(m: Dict[int | None, Dict[str, Any]], cid, cname, flag):
        if cid not in m:
            m[cid] = {
                "country": {
                    "id": cid,
                    "name": cname or "—",
                    "flag_filename": flag,
                    "slug": slugify_country(cname),
                },
                "items": [],
            }
        return m[cid]

    for r in rows:
        cid = r.country_id
        cname = r.country_name
        flag = r.flag_filename
        rec = {
            "stadium_id": r.stadium_id,
            "name": r.name,
            "city": r.city,
            "capacity": r.capacity,
            "opened_year": r.opened_year,
            "closed_year": r.closed_year,
            "photo_filename": r.photo_filename,
        }
        if r.closed_year is None:
            ensure_bucket(active_map, cid, cname, flag)["items"].append(rec)
        else:
            ensure_bucket(closed_map, cid, cname, flag)["items"].append(rec)

    # Sort by country name, then stadium name
    def sort_groups(m: Dict[int | None, Dict[str, Any]]) -> List[Dict[str, Any]]:
        arr = list(m.values())
        for g in arr:
            g["items"].sort(key=lambda s: (s["name"] or ""))
        return sorted(arr, key=lambda g: (g["country"]["name"] == "—", g["country"]["name"] or ""))

    active_grouped = sort_groups(active_map)
    closed_grouped = sort_groups(closed_map)

    return templates.TemplateResponse(
        "stadiums.html",
        {
            "request": request,
            "q": q,
            "status": status,
            "active_grouped": active_grouped,
            "closed_grouped": closed_grouped,
        },
    )

@router.get("/{stadium_id}", response_class=HTMLResponse, response_model=None)
def stadium_detail(request: Request, stadium_id: int, db: Session = Depends(get_db)):
    stmt = (
        select(
            Stadium.stadium_id,
            Stadium.name,
            Stadium.city,
            Stadium.capacity,
            Stadium.opened_year,
            Stadium.closed_year,
            Stadium.renovated_years,
            Stadium.tenants,
            Stadium.lat,
            Stadium.lng,
            Stadium.photo_filename,
            Country.country_id,
            Country.name.label("country_name"),
            Country.flag_filename.label("flag_filename"),
        )
        .join(Country, Country.country_id == Stadium.country_id, isouter=True)
        .where(Stadium.stadium_id == stadium_id)
    )
    r = db.execute(stmt).first()
    if not r:
        return RedirectResponse("/stadiums", status_code=303)

    country_slug = slugify_country(r.country_name)
    image_url = f"/static/images/stadiums/{country_slug}/{r.photo_filename}" if r.photo_filename else "/static/images/stadiums/stadium.png"

    return templates.TemplateResponse(
        "stadiums_detail.html",
        {
            "request": request,
            "stadium": {
                "id": r.stadium_id,
                "name": r.name,
                "city": r.city,
                "capacity": r.capacity,
                "opened_year": r.opened_year,
                "closed_year": r.closed_year,
                "renovated_years": r.renovated_years,
                "tenants": r.tenants,
                "lat": r.lat,
                "lng": r.lng,
                "image_url": image_url,
            },
            "country": {
                "id": r.country_id,
                "name": r.country_name,
                "flag_filename": r.flag_filename,
                "slug": country_slug,
            },
        },
    )
