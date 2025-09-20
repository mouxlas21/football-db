from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from ..db import get_db
from ..models import Person, Player, Country
from ..schemas import PlayerCreate, PlayerRead, PersonRead
from ..core.templates import templates

router = APIRouter(prefix="/players", tags=["players"])

@router.get("", response_class=HTMLResponse)
def players_page(
    request: Request,
    q: str | None = None,
    country: str | None = None,   # can be id / FIFA / name (optional filter)
    position: str | None = None,  # 'GK','DF','MF','FW'
    active: str | None = None,    # 'true' / 'false'
    limit: int = 200,
    db: Session = Depends(get_db),
):
    # Base query: we want Player rows, but we’ll join Person for filtering
    stmt = (
        select(Player, Person)
        .join(Person, Player.person_id == Person.person_id)
    )

    if q:
        stmt = stmt.where(func.lower(Person.full_name).like(f"%{q.strip().lower()}%"))

    if position:
        stmt = stmt.where(Player.player_position == position.strip().upper())

    if active in ("true", "false"):
        want = True if active == "true" else False
        stmt = stmt.where(Player.player_active == want)

    # Optional country filter (id or name/FIFA)
    if country:
        tok = country.strip()
        # try integer id
        try:
            cid = int(tok)
            stmt = stmt.where(Person.country_id == cid)
        except ValueError:
            # try FIFA code (upper) or name (case-insensitive)
            sub = select(Country.country_id).where(
                (Country.fifa_code == tok.upper()) |
                (func.lower(Country.name) == tok.lower())
            )
            stmt = stmt.where(Person.country_id.in_(sub))

    rows = db.execute(stmt.order_by(Person.full_name).limit(limit)).all()

    # Split back to lists and maps that the template expects
    player_list = [p for (p, _pe) in rows]
    person_ids = {pe.person_id for (_p, pe) in rows}
    persons_rows = db.execute(
        select(Person).where(Person.person_id.in_(person_ids))
    ).scalars().all()
    persons = {pe.person_id: pe for pe in persons_rows}

    # build countries map for the persons on the page
    country_ids = {pe.country_id for pe in persons_rows if pe.country_id}
    if country_ids:
        countries_rows = db.execute(
            select(Country).where(Country.country_id.in_(country_ids))
        ).scalars().all()
    else:
        countries_rows = []
    countries = {c.country_id: c for c in countries_rows}

    return templates.TemplateResponse(
        "players.html",
        {
            "request": request,
            "players": player_list,
            "persons": persons,
            "countries": countries,
            "q": q or "",
            "country": country or "",
            "position": position or "",
            "active": active,
            "limit": limit,
        },
    )

@router.get("/{player_id}", response_class=HTMLResponse)
def player_detail_page(player_id: int, request: Request, db: Session = Depends(get_db)):
    p = db.execute(select(Player).where(Player.player_id == player_id)).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Player not found")

    pe = db.execute(select(Person).where(Person.person_id == p.person_id)).scalar_one_or_none()

    country = None
    if pe and pe.country_id:
        country = db.execute(select(Country).where(Country.country_id == pe.country_id)).scalar_one_or_none()

    return templates.TemplateResponse(
        "player_detail.html",
        {
            "request": request,
            "player": p,
            "person": pe,
            "country": country,
        },
    )
