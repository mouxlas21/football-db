from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func
from ..db import get_db
from ..models import Team, Club, Country
from ..schemas import TeamRead, TeamCreate  # make sure TeamCreate exists (we shared a definition earlier)
from ..core.templates import templates

router = APIRouter(prefix="/teams", tags=["teams"])

@router.get("", response_class=HTMLResponse)
def teams_page(
    request: Request,
    q: str | None = Query(None),
    type: str | None = Query(None, description="club|national"),
    country_id: int | None = Query(None, description="Filter national teams by country_id"),
    club_id: int | None = Query(None, description="Filter club teams by club_id"),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    stmt = select(Team)
    conds = []

    if q:
        conds.append(Team.name.ilike(f"%{q.strip()}%"))

    if type:
        t = type.strip().lower()
        if t in ("club", "national"):
            conds.append(Team.type == t)

    if country_id:
        # Applies to national teams
        conds.append(and_(Team.national_country_id == country_id, Team.type == "national"))

    if club_id:
        # Applies to club teams
        conds.append(and_(Team.club_id == club_id, Team.type == "club"))

    if conds:
        stmt = stmt.where(and_(*conds))

    rows = db.execute(stmt.order_by(Team.type.asc(), Team.name.asc()).limit(limit)).scalars().all()

    # Hydrate related objects for display
    club_ids = {t.club_id for t in rows if t.club_id}
    country_ids = {t.national_country_id for t in rows if t.national_country_id}

    clubs_map = {}
    if club_ids:
        clubs = db.execute(select(Club).where(Club.club_id.in_(list(club_ids)))).scalars().all()
        clubs_map = {c.club_id: c for c in clubs}

    countries_map = {}
    if country_ids:
        countries = db.execute(select(Country).where(Country.country_id.in_(list(country_ids)))).scalars().all()
        countries_map = {c.country_id: c for c in countries}

    return templates.TemplateResponse(
        "teams.html",
        {
            "request": request,
            "teams": rows,
            "q": q or "",
            "type": type or "",
            "country_id": country_id,
            "club_id": club_id,
            "limit": limit,
            "clubs": clubs_map,
            "countries": countries_map,
        },
    )


@router.get("/{team_id}", response_class=HTMLResponse)
def team_detail_page(team_id: int, request: Request, db: Session = Depends(get_db)):
    t = db.execute(select(Team).where(Team.team_id == team_id)).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Team not found")

    club = None
    if t.club_id:
        club = db.execute(select(Club).where(Club.club_id == t.club_id)).scalar_one_or_none()

    country = None
    if t.national_country_id:
        country = db.execute(select(Country).where(Country.country_id == t.national_country_id)).scalar_one_or_none()

    return templates.TemplateResponse(
        "team_detail.html",
        {"request": request, "t": t, "club": club, "country": country},
    )


@router.get("/api", response_model=list[TeamRead])
def list_teams(
    q: str | None = None,
    type: str | None = None,
    country_id: int | None = None,
    club_id: int | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    stmt = select(Team)
    conds = []

    if q:
        conds.append(Team.name.ilike(f"%{q.strip()}%"))

    if type:
        t = type.strip().lower()
        if t in ("club", "national"):
            conds.append(Team.type == t)

    if country_id:
        conds.append(and_(Team.national_country_id == country_id, Team.type == "national"))

    if club_id:
        conds.append(and_(Team.club_id == club_id, Team.type == "club"))

    if conds:
        stmt = stmt.where(and_(*conds))

    rows = db.execute(stmt.order_by(Team.type.asc(), Team.name.asc()).limit(limit)).scalars().all()
    return [TeamRead.model_validate(r) for r in rows]


@router.post("/api", response_model=TeamRead)
def create_team(payload: TeamCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    ttype = (payload.type or "club").strip().lower()

    if ttype not in ("club", "national"):
        raise HTTPException(status_code=400, detail="type must be 'club' or 'national'")

    # XOR validation to match DB CHECK
    if ttype == "club":
        if not payload.club_id or payload.national_country_id:
            raise HTTPException(status_code=400, detail="club team requires club_id and must not set national_country_id")
    else:  # national
        if not payload.national_country_id or payload.club_id:
            raise HTTPException(status_code=400, detail="national team requires national_country_id and must not set club_id")

    # prevent duplicates by (name, type)
    exists = db.execute(
        select(Team).where(and_(func.lower(Team.name) == func.lower(name), Team.type == ttype))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="Team with same name and type already exists")

    row = Team(
        name=name,
        type=ttype,
        club_id=payload.club_id,
        national_country_id=payload.national_country_id,
        gender=payload.gender,
        age_group=payload.age_group,
        squad_level=payload.squad_level,
        logo_filename=payload.logo_filename,
    )

    db.add(row)
    db.commit()
    db.refresh(row)
    return TeamRead.model_validate(row)
