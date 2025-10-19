# backend/app/routers/countries.py
from typing import Optional, List, Dict, Tuple
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.templates import templates
from ..models import Country, Association, Competition, Team
from ..utils.comp_sort import international_sort_key

router = APIRouter(prefix="/countries", tags=["countries"])


@router.get("", response_class=HTMLResponse)
def countries_page(
    request: Request,
    q: Optional[str] = Query(None, description="Search by country name"),
    db: Session = Depends(get_db),
):
    base = select(Country)
    if q:
        q_like = f"%{q.strip()}%"
        base = base.where(Country.name.ilike(q_like))

    # If your status field differs, change here
    active_rows = db.execute(
        base.where(Country.c_status == "active").order_by(Country.name)
    ).scalars().all()

    hist_rows = db.execute(
        base.where(Country.c_status == "historical").order_by(Country.name)
    ).scalars().all()

    # Build confed map from both lists
    ass_ids = {c.confed_ass_id for c in (active_rows + hist_rows) if c.confed_ass_id}
    ass_map: Dict[int, Association] = {}
    if ass_ids:
        assocs = db.execute(
            select(Association).where(Association.ass_id.in_(ass_ids))
        ).scalars().all()
        ass_map = {a.ass_id: a for a in assocs}

    return templates.TemplateResponse(
        "countries.html",
        {
            "request": request,
            "q": q or "",
            "active_countries": active_rows,
            "historical_countries": hist_rows,
            "ass_map": ass_map,
        },
    )


@router.get("/{country_id}", response_class=HTMLResponse)
def country_detail_page(country_id: int, request: Request, db: Session = Depends(get_db)):
    # --- Country ---
    country: Optional[Country] = db.execute(
        select(Country).where(Country.country_id == country_id)
    ).scalar_one_or_none()
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")

    # --- Confederation association (if linked on country) ---
    association: Optional[Association] = None
    if getattr(country, "confed_ass_id", None):
        association = db.execute(
            select(Association).where(Association.ass_id == country.confed_ass_id)
        ).scalar_one_or_none()

    # --- Leagues (domestic) ---
    leagues: List[Competition] = db.execute(
        select(Competition)
        .where(Competition.country_id == country.country_id)
        .where(Competition.type.ilike("league"))
    ).scalars().all()
    leagues.sort(key=international_sort_key)

    # --- Cups (domestic) ---
    cups: List[Competition] = db.execute(
        select(Competition)
        .where(Competition.country_id == country.country_id)
        .where(Competition.type.ilike("cup"))
    ).scalars().all()
    cups.sort(key=international_sort_key)

    # --- National Teams ---
    teams: List[Team] = db.execute(
        select(Team)
        .where(Team.type == "national")
        .where(Team.national_country_id == country.country_id)
    ).scalars().all()

    # Helper predicates
    def is_women(t: Team) -> bool:
        g = (getattr(t, "gender", None) or "").lower()
        return g in ("w", "women", "female", "f")

    def is_youth(t: Team) -> bool:
        ag = (getattr(t, "age_group", None) or "").lower()
        # '', None, 'senior', 'open' => NOT youth
        return ag not in ("", None, "senior", "open")

    # Sorting helpers
    squad_order = {
        "first": 0,
        "senior": 0,     # sometimes used in data
        "reserve": 1,
        "reserves": 1,
        "b": 2,
        "u23": 3,
    }

    def senior_sort_key(t: Team) -> Tuple[int, str]:
        # order by squad_level (mapped) then by name
        lvl = (getattr(t, "squad_level", None) or "").lower()
        return (squad_order.get(lvl, 9), (getattr(t, "name", "") or "").lower())

    age_re = re.compile(r"(\d+)")
    def youth_age_value(ag: Optional[str]) -> int:
        if not ag:
            return 999
        s = ag.lower().replace("under-", "").replace("under ", "").replace("u-", "u")
        m = age_re.search(s)
        return int(m.group(1)) if m else 999

    def youth_sort_key(t: Team) -> Tuple[int, str]:
        ag = getattr(t, "age_group", None)
        return (youth_age_value(ag), (getattr(t, "name", "") or "").lower())

    # Bucket and sort
    nat = teams
    men_senior   = sorted([t for t in nat if not is_women(t) and not is_youth(t)], key=senior_sort_key)
    women_senior = sorted([t for t in nat if     is_women(t) and not is_youth(t)], key=senior_sort_key)
    men_youth    = sorted([t for t in nat if not is_women(t) and     is_youth(t)], key=youth_sort_key)
    women_youth  = sorted([t for t in nat if     is_women(t) and     is_youth(t)], key=youth_sort_key)

    national = {
        "men": men_senior,
        "women": women_senior,
        "men_youth": men_youth,
        "women_youth": women_youth,
    }

    # Provide a safe slug for competition thumbs folder
    def simple_slug(s: str) -> str:
        # very safe slug: alnum -> alnum lower, others -> hyphen, collapse repeats
        out = []
        prev_dash = False
        for ch in s.lower():
            if ch.isalnum():
                out.append(ch)
                prev_dash = False
            else:
                if not prev_dash:
                    out.append("-")
                    prev_dash = True
        slug = "".join(out).strip("-")
        return slug or "country"
    country_slug = getattr(country, "slug", None) or simple_slug(getattr(country, "name", "country"))

    fifa_png = (country.fifa_code.lower() + ".png") if getattr(country, "fifa_code", None) else None

    return templates.TemplateResponse(
        "country_detail.html",
        {
            "request": request,
            "country": country,
            "association": association,
            "leagues": leagues,
            "cups": cups,
            "national": national,
            "country_slug": country_slug,
            "fifa_png": fifa_png,
        },
    )
