# app/routers/confederations.py
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Association, Country, Competition
from ..core.templates import templates

router = APIRouter(prefix="/confederations", tags=["confederations"])

REGIONAL_CODES = ["AFC", "CAF", "CONCACAF", "CONMEBOL", "OFC", "UEFA"]  # fixed order
CONFED_CODES = {"FIFA", *REGIONAL_CODES}

def _is_confed_code(code: str | None) -> bool:
    return (code or "").strip().upper() in CONFED_CODES

@router.get("", response_class=HTMLResponse, response_model=None)
def confederations_page(
    request: Request,
    q: str | None = Query(None),
    db: Session = Depends(get_db),
):
    # FIFA (single)
    fifa_stmt = select(Association).where(Association.code == "FIFA")
    if q:
        like = f"%{q}%"
        fifa_stmt = fifa_stmt.where(Association.name.ilike(like) | Association.code.ilike(like))
    fifa = db.execute(fifa_stmt).scalars().first()

    # 6 regional confederations in fixed order
    regionals_stmt = select(Association).where(Association.code.in_(REGIONAL_CODES))
    if q:
        like = f"%{q}%"
        regionals_stmt = regionals_stmt.where(Association.name.ilike(like) | Association.code.ilike(like))
    regionals = db.execute(regionals_stmt).scalars().all()
    order_map = {c: i for i, c in enumerate(REGIONAL_CODES)}
    regionals.sort(key=lambda a: order_map.get(a.code, 999))

    return templates.TemplateResponse(
        "confederations.html",
        {
            "request": request,
            "q": q or "",
            "fifa": fifa,
            "regionals": regionals,
            "total": (1 if fifa else 0) + len(regionals),
        },
    )

@router.get("/{ass_id}", response_class=HTMLResponse, response_model=None)
def federation_detail(request: Request, ass_id: int, db: Session = Depends(get_db)):
    a = db.execute(select(Association).where(Association.ass_id == ass_id)).scalar_one_or_none()
    if not a or not _is_confed_code(a.code):
        raise HTTPException(status_code=404, detail="Confederation not found")

    code_norm = (a.code or "").strip().upper()
    is_fifa = code_norm == "FIFA"

    parent = None
    if not is_fifa:
        parent = db.execute(select(Association).where(Association.code == "FIFA")).scalar_one_or_none()

    # If FIFA → members are the six regional confeds
    children_confeds = []
    countries_active, countries_former = [], []

    if is_fifa:
        children_confeds = db.execute(
            select(Association).where(Association.code.in_(REGIONAL_CODES))
        ).scalars().all()
        # order them in the fixed order
        order_map = {c: i for i, c in enumerate(REGIONAL_CODES)}
        children_confeds.sort(key=lambda x: order_map.get((x.code or "").strip().upper(), 999))
    else:
        # For regional confeds → member countries
        countries_active = db.execute(
            select(Country)
            .where(Country.confed_ass_id == a.ass_id)
            .where(Country.c_status == "active")
            .order_by(Country.name.asc())
        ).scalars().all()
        countries_former = db.execute(
            select(Country)
            .where(Country.confed_ass_id == a.ass_id)
            .where(Country.c_status != "active")
            .order_by(Country.name.asc())
        ).scalars().all()

    # Competitions organized by this federation (best effort)
    comps = db.execute(
        select(Competition)
        .where(Competition.organizer_ass_id == a.ass_id)   # the organizer is this confed
        .where(Competition.country_id.is_(None))           # international only
        .order_by(Competition.name.asc())
    ).scalars().all()

    intl_club, intl_nat = [], []
    if comps and hasattr(Competition, "type"):
        for c in comps:
            t = (getattr(c, "type", "") or "").lower()
            if "club" in t:
                intl_club.append(c)
            elif "national" in t:
                intl_nat.append(c)
            else:
                intl_club.append(c)
    else:
        intl_club = comps

    return templates.TemplateResponse(
        "federation_detail.html",
        {
            "request": request,
            "a": a,
            "parent": parent,
            "is_fifa": is_fifa,
            "children_confeds": children_confeds,
            "countries_active": countries_active,
            "countries_former": countries_former,
            "intl_club": intl_club,
            "intl_nat": intl_nat,
        },
    )