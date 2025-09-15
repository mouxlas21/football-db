from pydantic import BaseModel, Field
from typing import Optional

class CountryCreate(BaseModel):
    name: str = Field(min_length=2)
    iso2: str | None = None

class CountryRead(BaseModel):
    country_id: int
    name: str
    iso2: str | None = None

class LeagueCreate(BaseModel):
    name: str = Field(..., min_length=2)
    country_id: int
    slug: Optional[str] = None
    tier: Optional[int] = None

class LeagueRead(BaseModel):
    league_id: int
    name: str
    country_id: int
    slug: Optional[str] = None
    tier: Optional[int] = None

    class Config:
        from_attributes = True
