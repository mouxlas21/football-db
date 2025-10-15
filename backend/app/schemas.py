from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import date, datetime

CountryStatus = Literal['active', 'historical']

class AssociationCreate(BaseModel):
    code: str
    name: str
    level: str
    logo_filename: Optional[str] = None
    parent_code: Optional[str] = None  

class AssociationRead(BaseModel):
    ass_id: int
    code: str
    name: str
    level: str
    logo_filename: Optional[str] = None
    parent_org_id: Optional[int] = None
    class Config: from_attributes = True

class CountryCreate(BaseModel):
    name: str
    flag_filename: Optional[str] = None
    fifa_code: Optional[str] = None
    confederation_code: Optional[str] = None
    c_status: Optional[str] = Field(default='active', pattern='^(active|historical)$')

class CountryRead(BaseModel):
    country_id: int
    name: str
    flag_filename: Optional[str] = None
    fifa_code: Optional[str] = None
    confed_ass_id: Optional[int] = None
    c_status: CountryStatus
    class Config: from_attributes = True
    
class StadiumCreate(BaseModel):
    name: str
    city: str
    country_id: Optional[int] = None
    capacity: Optional[int] = None
    opened_year: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    photo_filename: Optional[str] = None
    renovated_years: Optional[list[int]] = None      
    closed_year: Optional[int] = None
    tenants: Optional[list[str]] = None 

class StadiumRead(BaseModel):
    stadium_id: int
    name: str
    city: str
    country_id: Optional[int] = None
    capacity: Optional[int] = None
    opened_year: Optional[int] = None
    lat: Optional[float] = None 
    lng: Optional[float] = None
    photo_filename: Optional[str] = None
    renovated_years: Optional[list[int]] = None
    closed_year: Optional[int] = None
    tenants: Optional[list[str]] = None
    class Config: from_attributes = True

class CompetitionCreate(BaseModel):
    name: str
    type: str
    logo_filename: Optional[str] = None
    country_id: Optional[int] = None
    organizer_code: Optional[str] = None  

class CompetitionRead(BaseModel):
    competition_id: int
    name: str
    type: str
    logo_filename: Optional[str] = None
    country_id: Optional[int] = None
    organizer_ass_id: Optional[int] = None
    class Config: from_attributes = True
    
class ClubCreate(BaseModel):
    name: str = Field(..., min_length=2)
    short_name: Optional[str] = None
    founded: Optional[int] = None
    country_id: Optional[int] = None
    stadium_id: Optional[int] = None
    logo_filename: Optional[str] = None
    colors: Optional[str] = None

class ClubRead(BaseModel):
    club_id: int
    name: str
    short_name: Optional[str] = None
    founded: Optional[int] = None
    country_id: Optional[int] = None
    stadium_id: Optional[int] = None
    logo_filename: Optional[str] = None
    colors: Optional[str] = None
    class Config: from_attributes = True
    
class TeamCreate(BaseModel):
    name: str
    type: str                  
    club_id: Optional[int] = None      
    national_country_id: Optional[int] = None
    logo_filename: Optional[str] = None
    gender: Optional[str] = None
    age_group: Optional[str] = None
    squad_level: Optional[str] = None  

class TeamRead(BaseModel):
    team_id: int
    name: str
    type: str
    club_id: Optional[int] = None
    national_country_id: Optional[int] = None
    logo_filename: Optional[str] = None
    gender: Optional[str] = None
    age_group: Optional[str] = None
    squad_level: Optional[str] = None
    class Config: from_attributes = True

class FixtureCreate(BaseModel):
    stage_round_id: int
    home_team_id: int
    away_team_id: int
    kickoff_utc: datetime
    group_id: Optional[int] = None
    stadium_id: Optional[int] = None
    attendance: Optional[int] = None
    fixture_status: Optional[str] = "scheduled"

    ht_home_score: Optional[int] = None
    ht_away_score: Optional[int] = None
    ft_home_score: Optional[int] = None
    ft_away_score: Optional[int] = None
    et_home_score: Optional[int] = None
    et_away_score: Optional[int] = None
    pen_home_score: Optional[int] = None
    pen_away_score: Optional[int] = None

    went_to_extra_time: Optional[bool] = False
    went_to_penalties: Optional[bool] = False

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
    fixture_status: str

    ht_home_score: Optional[int] = None
    ht_away_score: Optional[int] = None
    ft_home_score: Optional[int] = None
    ft_away_score: Optional[int] = None
    et_home_score: Optional[int] = None
    et_away_score: Optional[int] = None
    pen_home_score: Optional[int] = None
    pen_away_score: Optional[int] = None

    went_to_extra_time: bool
    went_to_penalties: bool

    home_score: int
    away_score: int
    winner_team_id: Optional[int] = None

    class Config: from_attributes = True


class PersonCreate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: str
    known_as: Optional[str] = None
    birth_date: Optional[date] = None   
    birth_place: Optional[str] = None
    country_id: Optional[int] = None
    second_country_id: Optional[int] = None
    gender: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    photo_url: Optional[str] = None

class PersonRead(BaseModel):
    person_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: str
    known_as: Optional[str] = None
    birth_date: Optional[date] = None   
    birth_place: Optional[str] = None
    country_id: Optional[int] = None
    second_country_id: Optional[int] = None
    gender: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    photo_url: Optional[str] = None
    class Config: from_attributes = True

class PlayerCreate(BaseModel):
    person_id: Optional[int] = None         
    player_position: Optional[str] = None          # 'GK','DF','MF','FW'
    player_active: Optional[bool] = True

class PlayerRead(BaseModel):
    player_id: int
    person_id: Optional[int] = None
    player_position: Optional[str] = None
    player_active: bool
    class Config: from_attributes = True

class CoachCreate(BaseModel):
    person_id: Optional[int] = None
    role_default: Optional[str] = None
    coach_active: Optional[bool] = True

class CoachRead(BaseModel):
    coach_id: int
    person_id: Optional[int] = None
    role_default: Optional[str] = None
    coach_active: bool
    class Config: from_attributes = True

class OfficialCreate(BaseModel):
    person_id: Optional[int] = None
    association_id: Optional[int] = None   
    roles: Optional[str] = None
    official_active: Optional[bool] = True

class OfficialRead(BaseModel):
    official_id: int
    person_id: Optional[int] = None
    association_id: Optional[int] = None
    roles: Optional[str] = None
    official_active: bool
    class Config: from_attributes = True

class PlayerRegistrationCreate(BaseModel):
    player_id: int
    team_id: int
    start_date: date
    end_date: Optional[date] = None
    shirt_no: Optional[int] = None
    on_loan: Optional[bool] = False

class PlayerRegistrationRead(BaseModel):
    registration_id: int
    player_id: int
    team_id: int
    start_date: date
    end_date: Optional[date] = None
    shirt_no: Optional[int] = None
    on_loan: bool
    class Config: from_attributes = True

class StaffAssignmentCreate(BaseModel):
    person_id: int
    team_id: int
    staff_role: str
    start_date: date
    end_date: Optional[date] = None

class StaffAssignmentRead(BaseModel):
    assignment_id: int
    person_id: int
    team_id: int
    staff_role: str
    start_date: date
    end_date: Optional[date] = None
    class Config: from_attributes = True

class MatchOfficialCreate(BaseModel):
    fixture_id: int
    person_id: int
    duty: str

class MatchOfficialRead(BaseModel):
    match_official_id: int
    fixture_id: int
    person_id: int
    duty: str
    class Config: from_attributes = True
