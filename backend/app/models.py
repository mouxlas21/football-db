from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    SmallInteger,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .db import Base
from datetime import date, datetime

class Association(Base):
    __tablename__ = "association"

    ass_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code:   Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name:   Mapped[str] = mapped_column(Text, nullable=False)
    level:  Mapped[str] = mapped_column(Text, nullable=False)  # 'federation' | 'confederation' | 'association' | 'league_body'
    parent_org_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("association.ass_id", ondelete="SET NULL"))

class Country(Base):
    __tablename__ = "country"

    country_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    confed_ass_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("association.ass_id", ondelete="SET NULL"))
    fifa_code: Mapped[str | None] = mapped_column(String(3), unique=True)


class Stadium(Base):
    __tablename__ = "stadium"

    stadium_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str | None] = mapped_column(Text)
    country_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("country.country_id", ondelete="SET NULL"))
    capacity: Mapped[int | None] = mapped_column(Integer)
    opened_year: Mapped[int | None] = mapped_column(SmallInteger)
    lat: Mapped[float | None] = mapped_column()
    lng: Mapped[float | None] = mapped_column()


class Club(Base):
    __tablename__ = "club"

    club_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)  # global unique by schema
    short_name: Mapped[str | None] = mapped_column(Text)
    founded: Mapped[int | None] = mapped_column(SmallInteger)
    country_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("country.country_id", ondelete="SET NULL"))
    stadium_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("stadium.stadium_id", ondelete="SET NULL"))
    colors: Mapped[str | None] = mapped_column(Text)

    country = relationship("Country")
    stadium = relationship("Stadium")

    __table_args__ = (
        Index("ix_club_country", "country_id"),
        Index("ix_club_stadium", "stadium_id"),
    )

class Competition(Base):
    __tablename__ = "competition"

    competition_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)  # 'league' | 'cup' | ...
    country_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("country.country_id", ondelete="SET NULL"))
    confed_ass_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("association.ass_id", ondelete="SET NULL"))
class Person(Base):
    __tablename__ = "person"

    person_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    known_as: Mapped[str | None] = mapped_column(Text)
    dob: Mapped[date | None] = mapped_column(Date)
    country_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("country.country_id", ondelete="SET NULL"))
    height_cm: Mapped[int | None] = mapped_column(SmallInteger)
    weight_kg: Mapped[int | None] = mapped_column(SmallInteger)

class Player(Base):
    __tablename__ = "player"

    player_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id", ondelete="CASCADE"), primary_key=True)
    foot: Mapped[str | None] = mapped_column(Text)
    primary_position: Mapped[str | None] = mapped_column(Text)

    person = relationship("Person", backref="player", uselist=False)

class Team(Base):
    __tablename__ = "team"

    team_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False, default="club")
    club_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("club.club_id", ondelete="SET NULL"))
    national_country_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("country.country_id", ondelete="SET NULL"))

class Fixture(Base):
    __tablename__ = "fixture"
    fixture_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # FK to stage_round
    stage_round_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stage_round.stage_round_id", ondelete="CASCADE"), nullable=False)
    # FK to stage_group (nullable)
    group_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("stage_group.group_id", ondelete="SET NULL"))
    home_team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("team.team_id", ondelete="RESTRICT"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("team.team_id", ondelete="RESTRICT"), nullable=False)
    kickoff_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stadium_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("stadium.stadium_id", ondelete="SET NULL"))
    attendance: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="scheduled")
    home_score: Mapped[int] = mapped_column(SmallInteger, default=0)
    away_score: Mapped[int] = mapped_column(SmallInteger, default=0)
    winner_team_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("team.team_id", ondelete="SET NULL"))

class Season(Base):
    __tablename__ = "season"
    season_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    competition_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("competition.competition_id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)

class Stage(Base):
    __tablename__ = "stage"
    stage_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    season_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("season.season_id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    stage_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    format: Mapped[str] = mapped_column(Text, nullable=False)

class StageRound(Base):
    __tablename__ = "stage_round"
    stage_round_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stage_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stage.stage_id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    stage_round_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    two_legs: Mapped[bool] = mapped_column(default=False)
