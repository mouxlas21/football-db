from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from ..db import get_db
from ..models import Association, Competition
from ..core.templates import templates

router = APIRouter(prefix="/associations", tags=["associations"])

@router.get("", response_class=HTMLResponse)
def associations_page(request: Request, q: str | None = Query(None), db: Session = Depends(get_db)):
    stmt = select(Association)
    if q:
        stmt = stmt.where(Association.name.ilike(f"%{q}%") | Association.code.ilike(f"%{q}%"))
    rows = db.execute(stmt.order_by(Association.level, Association.code)).scalars().all()
    return templates.TemplateResponse("associations.html", {"request": request, "rows": rows, "q": q or ""})

@router.get("/{ass_id}", response_class=HTMLResponse)
def association_detail(
    ass_id: int,
    request: Request,
    include_children: bool = Query(False),
    db: Session = Depends(get_db)
):
    a = db.execute(select(Association).where(Association.ass_id == ass_id)).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Association not found")

    parent = None
    if a.parent_org_id:
        parent = db.execute(select(Association).where(Association.ass_id == a.parent_org_id)).scalar_one_or_none()

    children = db.execute(select(Association).where(Association.parent_org_id == a.ass_id)).scalars().all()

    # Competitions directly organized by this association
    comps_stmt = (
        select(Competition)
        .where(Competition.organizer_ass_id == a.ass_id)
        .order_by(Competition.name.asc())
    )
    comps = db.execute(comps_stmt).scalars().all()

    # Optionally include competitions from child associations
    child_comps = []
    if include_children and children:
        child_ids = [c.ass_id for c in children]
        child_comps = db.execute(
            select(Competition)
            .where(Competition.organizer_ass_id.in_(child_ids))
            .order_by(Competition.name.asc())
        ).scalars().all()

    # Split into buckets
    # Heuristic:
    # - International = competitions with country_id IS NULL
    # - Domestic     = competitions with a country_id (organized by a national FA)
    internationals = [c for c in comps if c.country_id is None]
    domestics      = [c for c in comps if c.country_id is not None]

    # If model has participant_type (club/national), split international further
    has_participant_type = hasattr(Competition, "participant_type")
    intl_club = []
    intl_nat  = []
    if has_participant_type:
        intl_club = [c for c in internationals if (c.participant_type or "").lower() == "club"]
        intl_nat  = [c for c in internationals if (c.participant_type or "").lower() != "club"]
    else:
        # Fallback: put all internationals together
        intl_club = internationals
        intl_nat  = []

    # For child orgs, you can either merge or show separately; here we keep a single list:
    child_internationals = [c for c in child_comps if c.country_id is None]
    child_domestics      = [c for c in child_comps if c.country_id is not None]

    return templates.TemplateResponse(
        "association_detail.html",
        {
            "request": request,
            "a": a,
            "parent": parent,
            "children": children,
            "intl_club": intl_club,
            "intl_nat": intl_nat,
            "domestics": domestics,
            "has_participant_type": has_participant_type,
            "include_children": include_children,
            "child_internationals": child_internationals,
            "child_domestics": child_domestics,
        },
    )