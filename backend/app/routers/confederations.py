# app/routers/confederations.py
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select, Table, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Association, Country, Competition
from ..core.templates import templates
from ..utils.comp_sort import international_sort_key

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
    if not a:
        raise HTTPException(status_code=404, detail="Association not found")

    level = (a.level or "").strip().lower()  # 'federation' | 'confederation' | 'sub_confederation'
    is_fifa = (a.code or "").strip().upper() == "FIFA"

    # association_parent table for parent/children
    association_parent = Table("association_parent", Association.metadata, autoload_with=db.bind)

    # --- Parent (dynamic via association_parent) ---
    parents = db.execute(
        select(Association)
        .join(association_parent, association_parent.c.parent_ass_id == Association.ass_id)
        .where(association_parent.c.ass_id == a.ass_id)
        .order_by(Association.code.asc())
    ).scalars().all()

    # --- Children (dynamic via association_parent) ---
    children = db.execute(
        select(Association)
        .join(association_parent, association_parent.c.ass_id == Association.ass_id)
        .where(association_parent.c.parent_ass_id == a.ass_id)
        .order_by(Association.code.asc())
    ).scalars().all()

    # map children to the right buckets for the template
    children_confeds = children if level == "federation" else []      # FIFA: shows regional confeds in Members
    sub_confeds      = children if level == "confederation" else []    # Confed: shows sub-confeds inline under Parent

    # --- Members (countries) ---
    countries_active, countries_former = [], []

    if level in ("confederation", "sub_confederation"):
        if level == "sub_confederation":
            country_sub_confed = Table("country_sub_confed", Association.metadata, autoload_with=db.bind)

            countries_active = db.execute(
                select(Country)
                .join(country_sub_confed, country_sub_confed.c.country_id == Country.country_id)
                .where(country_sub_confed.c.sub_confed_ass_id == a.ass_id)
                .where(Country.c_status == "active")
                .order_by(Country.name.asc())
            ).scalars().all()

            countries_former = db.execute(
                select(Country)
                .join(country_sub_confed, country_sub_confed.c.country_id == Country.country_id)
                .where(country_sub_confed.c.sub_confed_ass_id == a.ass_id)
                .where(Country.c_status != "active")
                .order_by(Country.name.asc())
            ).scalars().all()
        else:
            countries_active = db.execute(
                select(Country)
                .where(Country.confed_ass_id == a.ass_id, Country.c_status == "active")
                .order_by(Country.name.asc())
            ).scalars().all()

            countries_former = db.execute(
                select(Country)
                .where(Country.confed_ass_id == a.ass_id, Country.c_status != "active")
                .order_by(Country.name.asc())
            ).scalars().all()

    # --- Competitions (international only) with images for the cards ---
    comps = db.execute(
        select(Competition)
        .where(Competition.organizer_ass_id == a.ass_id)
        .where(Competition.country_id.is_(None))
        .order_by(Competition.name.asc())
    ).scalars().all()

    img_base = f"federations/{(a.code or '').strip().lower()}"
    intl_vm = [{
        "id": c.competition_id,
        "name": c.name,
        "type": c.type,
        "tier": c.tier,
        "cup_rank": c.cup_rank,
        "gender": c.gender,
        "age_group": c.age_group,
        "filename": getattr(c, "logo_filename", None),
        "image_base": img_base,
    } for c in comps]
    intl_sorted = sorted(intl_vm, key=international_sort_key)

    return templates.TemplateResponse(
        "federation_detail.html",
        {
            "request": request,
            "a": a,
            "level": level,
            "is_fifa": is_fifa,
            "parents": parents,                      # now dynamic
            "children_confeds": children_confeds,  # only for federation level
            "sub_confeds": sub_confeds,            # only for confederation level
            "countries_active": countries_active,  # confed or sub_confed
            "countries_former": countries_former,  # confed or sub_confed
            "intl_sorted": intl_sorted,
        },
    )
