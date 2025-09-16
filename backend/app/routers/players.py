from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, join
from ..db import get_db
from ..models import Person, Player, Country
from ..schemas import PlayerCreate, PlayerRead, PersonCreate, PersonRead
from ..core.templates import templates

router = APIRouter(prefix="/players", tags=["players"])

@router.get("", response_class=HTMLResponse)
def players_page(
    request: Request,
    q: str | None = None,
    country_id: int | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Player, Person).join(Person, Player.player_id == Person.person_id)
    if q:
        stmt = stmt.where(Person.full_name.ilike(f"%{q.strip()}%"))
    if country_id:
        stmt = stmt.where(Person.country_id == country_id)

    rows = db.execute(stmt.order_by(Person.full_name)).all()

    countries = db.execute(select(Country.country_id, Country.name).order_by(Country.name)).all()
    country_map = {cid: cname for cid, cname in countries}

    # rows is list of tuples (Player, Person)
    players = [{"player": p, "person": pe} for p, pe in rows]

    return templates.TemplateResponse(
        "players.html",
        {"request": request, "players": players, "q": q or "", "country_id": country_id, "country_map": country_map},
    )

@router.get("/{player_id}", response_class=HTMLResponse)
def player_detail_page(player_id: int, request: Request, db: Session = Depends(get_db)):
    player = db.execute(select(Player).where(Player.player_id == player_id)).scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    person = db.execute(select(Person).where(Person.person_id == player.player_id)).scalar_one_or_none()
    country = None
    if person and person.country_id:
        country = db.execute(select(Country).where(Country.country_id == person.country_id)).scalar_one_or_none()
    return templates.TemplateResponse(
        "player_detail.html",
        {"request": request, "player": player, "person": person, "country": country},
    )

# --- JSON API ---

@router.get("/api", response_model=list[PlayerRead])
def api_list_players(
    q: str | None = None,
    country_id: int | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    stmt = select(Player, Person).join(Person, Player.player_id == Person.person_id)
    if q:
        stmt = stmt.where(Person.full_name.ilike(f"%{q.strip()}%"))
    if country_id:
        stmt = stmt.where(Person.country_id == country_id)
    rows = db.execute(stmt.order_by(Person.full_name).limit(limit)).all()
    out: list[PlayerRead] = []
    for p, pe in rows:
        out.append(PlayerRead(
            player_id=p.player_id,
            foot=p.foot,
            primary_position=p.primary_position,
            person=PersonRead(
                person_id=pe.person_id, full_name=pe.full_name, known_as=pe.known_as, dob=pe.dob,
                country_id=pe.country_id, height_cm=pe.height_cm, weight_kg=pe.weight_kg
            )
        ))
    return out

@router.get("/api/{player_id}", response_model=PlayerRead)
def api_get_player(player_id: int, db: Session = Depends(get_db)):
    p = db.execute(select(Player).where(Player.player_id == player_id)).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Player not found")
    pe = db.execute(select(Person).where(Person.person_id == p.player_id)).scalar_one_or_none()
    return PlayerRead(
        player_id=p.player_id,
        foot=p.foot,
        primary_position=p.primary_position,
        person=PersonRead(
            person_id=pe.person_id, full_name=pe.full_name, known_as=pe.known_as, dob=pe.dob,
            country_id=pe.country_id, height_cm=pe.height_cm, weight_kg=pe.weight_kg
        )
    )

@router.post("/api", response_model=PlayerRead)
def api_create_player(payload: PlayerCreate, db: Session = Depends(get_db)):
    # If person_id is provided, ensure it exists
    if payload.person_id:
        pe = db.execute(select(Person).where(Person.person_id == payload.person_id)).scalar_one_or_none()
        if not pe:
            raise HTTPException(status_code=400, detail="person_id not found")
        person_id = pe.person_id
    else:
        # Create a new person from nested payload.person
        if not payload.person or not payload.person.full_name:
            raise HTTPException(status_code=400, detail="Provide either person_id or person with full_name")
        pe = Person(
            full_name=payload.person.full_name.strip(),
            known_as=(payload.person.known_as or None),
            dob=payload.person.dob,
            country_id=payload.person.country_id,
            height_cm=payload.person.height_cm,
            weight_kg=payload.person.weight_kg,
        )
        db.add(pe)
        db.flush()  # get new person_id
        person_id = pe.person_id

    # Create the player row (PK equals person_id)
    existing = db.execute(select(Player).where(Player.player_id == person_id)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Player already exists for this person")

    pl = Player(
        player_id=person_id,
        foot=payload.foot,
        primary_position=payload.primary_position,
    )
    db.add(pl)
    db.commit()
    db.refresh(pl)

    # Build response
    if not payload.person_id:
        # person created in this transaction; pe is available
        pe_resp = pe
    else:
        pe_resp = db.execute(select(Person).where(Person.person_id == person_id)).scalar_one_or_none()

    return PlayerRead(
        player_id=pl.player_id,
        foot=pl.foot,
        primary_position=pl.primary_position,
        person=PersonRead(
            person_id=pe_resp.person_id, full_name=pe_resp.full_name, known_as=pe_resp.known_as, dob=pe_resp.dob,
            country_id=pe_resp.country_id, height_cm=pe_resp.height_cm, weight_kg=pe_resp.weight_kg
        )
    )