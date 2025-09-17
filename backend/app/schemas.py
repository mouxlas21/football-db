from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime

class CountryRead(BaseModel):
    country_id: int
    name: str
    iso2: Optional[str] = None

    class Config:
        from_attributes = True


class CountryCreate(BaseModel):
    name: str = Field(..., min_length=2)
    iso2: Optional[str] = None


class ClubCreate(BaseModel):
    name: str = Field(..., min_length=2)
    short_name: Optional[str] = None
    founded: Optional[int] = None
    country_id: Optional[int] = None
    stadium_id: Optional[int] = None
    colors: Optional[str] = None


class ClubRead(BaseModel):
    club_id: int
    name: str
    short_name: Optional[str] = None
    founded: Optional[int] = None
    country_id: Optional[int] = None
    stadium_id: Optional[int] = None
    colors: Optional[str] = None

    class Config:
        from_attributes = True


class CompetitionCreate(BaseModel):
    name: str = Field(..., min_length=2)
    type: Optional[str] = "league"      # 'league' | 'cup' | ...
    organizer: Optional[str] = None
    country_id: Optional[int] = None
    confederation: Optional[str] = None


class CompetitionRead(BaseModel):
    competition_id: int
    name: str
    type: str
    organizer: Optional[str] = None
    country_id: Optional[int] = None
    confederation: Optional[str] = None

    @classmethod
    def from_model(cls, m):
        return cls(
            competition_id=m.competition_id,
            name=m.name,
            type=m.type,
            organizer=m.organizer,
            country_id=m.country_id,
            confederation=m.confederation,
        )

    class Config:
        from_attributes = True


# Backwards-compatible league API models (if you still use /leagues JSON)
class LeagueCreate(CompetitionCreate):
    type: Optional[str] = "league"


class LeagueRead(BaseModel):
    league_id: int
    name: str
    organizer: Optional[str] = None
    country_id: Optional[int] = None
    confederation: Optional[str] = None

    @classmethod
    def model_validate_from_competition(cls, c):
        return cls(
            league_id=c.competition_id,
            name=c.name,
            organizer=c.organizer,
            country_id=c.country_id,
            confederation=c.confederation,
        )

    class Config:
        from_attributes = True
        
class PersonCreate(BaseModel):
    full_name: str
    known_as: Optional[str] = None
    dob: Optional[date] = None
    country_id: Optional[int] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None

class PersonRead(BaseModel):
    person_id: int
    full_name: str
    known_as: Optional[str] = None
    dob: Optional[date] = None
    country_id: Optional[int] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    class Config:
        from_attributes = True

class PlayerCreate(BaseModel):
    person_id: Optional[int] = None
    person: Optional[PersonCreate] = None
    foot: Optional[str] = None
    primary_position: Optional[str] = None

class PlayerRead(BaseModel):
    player_id: int
    foot: Optional[str] = None
    primary_position: Optional[str] = None
    person: PersonRead
    class Config:
        from_attributes = True

class TeamRead(BaseModel):
    team_id: int
    name: str
    type: str
    club_id: Optional[int] = None
    national_country_id: Optional[int] = None
    class Config:
        from_attributes = True

class FixtureCreate(BaseModel):
    stage_round_id: int
    home_team_id: int
    away_team_id: int
    kickoff_utc: datetime
    group_id: Optional[int] = None
    stadium_id: Optional[int] = None
    attendance: Optional[int] = None
    status: Optional[str] = "scheduled"
    home_score: Optional[int] = 0
    away_score: Optional[int] = 0
    winner_team_id: Optional[int] = None

class FixtureRead(BaseModel):
    fixture_id: int
    stage_round_id: int
    group_id: Optional[int] = None
    home_team_id: int
    away_team_id: int
    kickoff_utc: datetime
    stadium_id: Optional[int] = None
    attendance: Optional[int] = None
    status: str
    home_score: int
    away_score: int
    winner_team_id: Optional[int] = None

    class Config:
        from_attributes = True