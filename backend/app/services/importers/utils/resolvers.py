from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_
from app.models import Country, Association, Club, Stadium, Team
from .helpers import _to_int

# --- Countries ---

def resolve_country_id(token, db: Session) -> Optional[int]:
    """
    Accepts: numeric id | FIFA code | country name (case-insensitive).
    Returns country_id or None.
    """
    if token is None:
        return None
    as_int = _to_int(token)
    if as_int is not None:
        return as_int
    val = str(token).strip()
    if not val:
        return None

    row = db.execute(select(Country).where(Country.fifa_code == val.upper())).scalar_one_or_none()
    if row:
        return row.country_id

    row = db.execute(select(Country).where(func.lower(Country.name) == func.lower(val))).scalar_one_or_none()
    return row.country_id if row else None

# --- Associations (FIFA/UEFA/… by code or name) ---

def resolve_association_id(token, db: Session) -> Optional[int]:
    """
    Accepts: numeric id | association code (e.g., 'UEFA') | association name (case-insensitive).
    """
    if token is None:
        return None
    as_int = _to_int(token)
    if as_int is not None:
        return as_int
    val = str(token).strip()
    if not val:
        return None

    row = db.execute(select(Association).where(Association.code == val.upper())).scalar_one_or_none()
    if row:
        return row.ass_id

    row = db.execute(select(Association).where(func.lower(Association.name) == func.lower(val))).scalar_one_or_none()
    return row.ass_id if row else None

# --- Clubs (id or name) ---

def resolve_club_id(token, db: Session) -> Optional[int]:
    if token is None:
        return None
    as_int = _to_int(token)
    if as_int is not None:
        return as_int
    val = str(token).strip()
    if not val:
        return None

    row = db.execute(select(Club).where(func.lower(Club.name) == func.lower(val))).scalar_one_or_none()
    return row.club_id if row else None

# --- Stadiums (id, or name+city, or name+country, or globally-unique name) ---

def resolve_stadium_id(token, db: Session, city_hint: str | None = None, country_id_hint: int | None = None) -> Optional[int]:
    if token is None:
        return None
    as_int = _to_int(token)
    if as_int is not None:
        return as_int
    val = str(token).strip()
    if not val:
        return None

    if city_hint:
        row = db.execute(
            select(Stadium).where(
                and_(
                    func.lower(Stadium.name) == func.lower(val),
                    func.lower(Stadium.city) == func.lower(city_hint.strip())
                )
            )
        ).scalar_one_or_none()
        if row:
            return row.stadium_id

    if country_id_hint:
        rows = db.execute(
            select(Stadium).where(
                and_(
                    func.lower(Stadium.name) == func.lower(val),
                    Stadium.country_id == country_id_hint
                )
            )
        ).scalars().all()
        if len(rows) == 1:
            return rows[0].stadium_id

    rows = db.execute(select(Stadium).where(func.lower(Stadium.name) == func.lower(val))).scalars().all()
    if len(rows) == 1:
        return rows[0].stadium_id

    return None

# --- Teams (several common cases) ---

def resolve_team_id(
    token,
    db: Session,
    *,
    type_hint: str | None = None,
    club_id: int | None = None,
    national_country_id: int | None = None,
    age_group: str | None = None,
    gender: str | None = None,
) -> Optional[int]:
    """
    Flexible resolver to find team by:
      - numeric id (fast path), or
      - club bucket (type='club', club_id, optional exact name), or
      - national bucket (type='national', country + age_group + gender),
      - fallback by exact name (case-insensitive) if unique.
    """
    if token is not None:
        as_int = _to_int(token)
        if as_int is not None:
            return as_int
        name = str(token).strip()
    else:
        name = None

    # If the caller knows it's club team
    if type_hint == "club" and club_id is not None:
        row = db.execute(
            select(Team).where(and_(Team.type == "club", Team.club_id == club_id))
        ).scalar_one_or_none()
        if row:
            return row.team_id

    # If the caller knows it's a national team bucket
    if type_hint == "national" and national_country_id is not None:
        row = db.execute(
            select(Team).where(
                and_(
                    Team.type == "national",
                    Team.national_country_id == national_country_id,
                    (Team.age_group == age_group) if age_group is not None else Team.age_group.is_(None),
                    (Team.gender == gender) if gender is not None else Team.gender.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row:
            return row.team_id

    # Name-only fallback (only if globally unique)
    if name:
        rows = db.execute(select(Team).where(func.lower(Team.name) == func.lower(name))).scalars().all()
        if len(rows) == 1:
            return rows[0].team_id

    return None
