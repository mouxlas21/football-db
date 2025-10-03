from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select, func
from ..db import get_session
from ..models import Team, TeamAlias  # adjust names

router = APIRouter(prefix="/api/reference", tags=["reference"])

class TeamOut(BaseModel):
    id: int
    name: str
    aliases: List[str] = []

@router.get("/teams", response_model=List[TeamOut])
def list_teams(competition: Optional[str] = None,
               country: Optional[str] = None,
               session = Depends(get_session)):
    # Build your query; filter by competition/country if you want
    q = select(Team.id, Team.name)
    rows = session.execute(q).all()
    ids = [r[0] for r in rows]
    # fetch aliases per team (optimize as a single query in your codebase)
    alias_map = {tid: [] for tid in ids}
    for (tid, alias) in session.execute(select(TeamAlias.team_id, TeamAlias.alias)).all():
        alias_map.setdefault(tid, []).append(alias)
    return [TeamOut(id=r[0], name=r[1], aliases=alias_map.get(r[0], [])) for r in rows]
