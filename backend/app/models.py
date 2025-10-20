from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    Table,
    Column,
    Text,
    Date,
    DateTime,
    func,
    SmallInteger,
    ForeignKey,
    Index,
    Enum,
    UniqueConstraint,
    PrimaryKeyConstraint,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import ARRAY

from .db import Base
from datetime import date, datetime

association_parent = Table(
    "association_parent",
    Base.metadata,
    Column("ass_id", BigInteger, ForeignKey("association.ass_id", ondelete="CASCADE"), nullable=False),
    Column("parent_ass_id", BigInteger, ForeignKey("association.ass_id", ondelete="CASCADE"), nullable=False),
    PrimaryKeyConstraint("ass_id", "parent_ass_id"),
)

class Association(Base):
    __tablename__ = "association"

    ass_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code:   Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name:   Mapped[str] = mapped_column(Text, nullable=False)
    founded_year: Mapped[int | None] = mapped_column(SmallInteger)
    level:  Mapped[str] = mapped_column(Text, nullable=False)  
    logo_filename: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now, server_default=func.now(),)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now, server_default=func.now(), onupdate=func.now(),)

    parents = relationship(
        "Association",
        secondary=association_parent,
        primaryjoin=lambda: Association.ass_id == association_parent.c.ass_id,
        secondaryjoin=lambda: Association.ass_id == association_parent.c.parent_ass_id,
        backref="children",
        lazy="selectin",
    )

class CountrySubConfed(Base):
    __tablename__ = "country_sub_confed"
    country_id: Mapped[int] = mapped_column(ForeignKey("country.country_id", ondelete="CASCADE"), primary_key=True)
    sub_confed_ass_id: Mapped[int] = mapped_column(ForeignKey("association.ass_id", ondelete="CASCADE"), primary_key=True)

class Country(Base):
    __tablename__ = "country"

    country_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    nat_association: Mapped[str | None] = mapped_column(Text)
    flag_filename: Mapped[str | None] = mapped_column(Text)
    confed_ass_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("association.ass_id", ondelete="SET NULL"))
    fifa_code: Mapped[str | None] = mapped_column(String(3), unique=True)
    sub_confederations: Mapped[list["Association"]] = relationship("Association", secondary="country_sub_confed", primaryjoin="Country.country_id==CountrySubConfed.country_id", secondaryjoin="CountrySubConfed.sub_confed_ass_id==Association.ass_id", viewonly=True,)
    c_status: Mapped[str] = mapped_column(Enum("active", "historical", name="country_status", create_type=False), nullable=False, server_default="active",)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now, server_default=func.now(), onupdate=func.now())

class Stadium(Base):
    __tablename__ = "stadium"

    stadium_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str | None] = mapped_column(Text)
    country_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("country.country_id", ondelete="SET NULL"))
    capacity: Mapped[int | None] = mapped_column(Integer)
    opened_year: Mapped[int | None] = mapped_column(SmallInteger)
    photo_filename: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column()
    lng: Mapped[float | None] = mapped_column()
    renovated_years: Mapped[list[int] | None] = mapped_column(ARRAY(SmallInteger))
    closed_year: Mapped[int | None] = mapped_column(SmallInteger)
    tenants: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now, server_default=func.now(),)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now, server_default=func.now(), onupdate=func.now(),)

class Competition(Base):
    __tablename__ = "competition"

    competition_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)          
    tier: Mapped[int | None] = mapped_column(SmallInteger)
    cup_rank: Mapped[str | None] = mapped_column(Text)                  
    gender: Mapped[str | None] = mapped_column(Text)
    age_group: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text)
    logo_filename: Mapped[str | None] = mapped_column(Text)
    country_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("country.country_id", ondelete="SET NULL"))
    organizer_ass_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("association.ass_id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now, server_default=func.now(),)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now, server_default=func.now(), onupdate=func.now(),)

    __table_args__ = (
        UniqueConstraint("name", "country_id", "organizer_ass_id", name="uq_comp_name_country_org"),
        Index("idx_comp_country", "country_id"),
        Index("idx_comp_organizer", "organizer_ass_id"),
        Index("idx_comp_type_tier", "type", "tier"),
    )

class Club(Base):
    __tablename__ = "club"

    club_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)  # global unique by schema
    short_name: Mapped[str | None] = mapped_column(Text)
    founded: Mapped[int | None] = mapped_column(SmallInteger)
    country_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("country.country_id", ondelete="SET NULL"))
    stadium_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("stadium.stadium_id", ondelete="SET NULL"))
    logo_filename: Mapped[str | None] = mapped_column(Text)
    colors: Mapped[str | None] = mapped_column(Text)

    country = relationship("Country")
    stadium = relationship("Stadium")

    __table_args__ = (
        Index("ix_club_country", "country_id"),
        Index("ix_club_stadium", "stadium_id"),
    )

class Team(Base):
    __tablename__ = "team"

    team_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False, default="club")
    club_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("club.club_id", ondelete="SET NULL"))
    national_country_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("country.country_id", ondelete="SET NULL"))
    logo_filename: Mapped[str | None] = mapped_column(Text)
    gender: Mapped[str | None] = mapped_column(Text)
    age_group: Mapped[str | None] = mapped_column(Text)
    squad_level: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now, server_default=func.now(),)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now, server_default=func.now(), onupdate=func.now(),)

class Person(Base):
    __tablename__ = "person"

    person_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    known_as: Mapped[str | None] = mapped_column(Text)
    birth_date: Mapped[date | None] = mapped_column(Date)  # was dob
    birth_place: Mapped[str | None] = mapped_column(Text)
    country_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("country.country_id", ondelete="SET NULL"))
    second_country_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("country.country_id", ondelete="SET NULL"))
    gender: Mapped[str | None] = mapped_column(Text)
    height_cm: Mapped[int | None] = mapped_column(SmallInteger)
    weight_kg: Mapped[int | None] = mapped_column(SmallInteger)
    photo_url: Mapped[str | None] = mapped_column(Text)

class Player(Base):
    __tablename__ = "player"

    player_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id", ondelete="CASCADE"))
    player_position: Mapped[str | None] = mapped_column(Text)  # 'GK','DF','MF','FW'
    player_active: Mapped[bool] = mapped_column(default=True)

    person = relationship("Person", backref="player", uselist=False)

class Coach(Base):
    __tablename__ = "coach"

    coach_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id", ondelete="CASCADE"), unique=True, nullable=False)
    role_default: Mapped[str | None] = mapped_column(Text)  # 'head','assistant','gk','fitness',...
    coach_active: Mapped[bool] = mapped_column(default=True)

    person = relationship("Person", backref="coach", uselist=False)

class Official(Base):
    __tablename__ = "official"

    official_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id", ondelete="CASCADE"), unique=True, nullable=False)
    association_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("association.ass_id", ondelete="SET NULL"))
    roles: Mapped[str | None] = mapped_column(Text)  # e.g. 'referee;assistant;VAR'
    official_active: Mapped[bool] = mapped_column(default=True)

    person = relationship("Person", backref="official", uselist=False)

class PlayerRegistration(Base):
    __tablename__ = "player_registration"

    registration_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("player.player_id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("team.team_id", ondelete="CASCADE"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    shirt_no: Mapped[int | None] = mapped_column(SmallInteger)
    on_loan: Mapped[bool] = mapped_column(default=False)

class StaffAssignment(Base):
    __tablename__ = "staff_assignment"

    assignment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("team.team_id", ondelete="CASCADE"), nullable=False)
    staff_role: Mapped[str] = mapped_column(Text, nullable=False)  # 'head coach','assistant','gk coach',...
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)

class MatchOfficial(Base):
    __tablename__ = "match_official"

    match_official_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("fixture.fixture_id", ondelete="CASCADE"), nullable=False)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id", ondelete="CASCADE"), nullable=False)
    duty: Mapped[str] = mapped_column(Text, nullable=False)  # 'referee','AR1','AR2','4th','VAR','AVAR'


class Fixture(Base):
    __tablename__ = "fixture"

    fixture_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stage_round_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stage_round.stage_round_id", ondelete="CASCADE"), nullable=False)
    group_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("stage_group.group_id", ondelete="SET NULL"))

    home_team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("team.team_id", ondelete="RESTRICT"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("team.team_id", ondelete="RESTRICT"), nullable=False)
    kickoff_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stadium_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("stadium.stadium_id", ondelete="SET NULL"))
    attendance: Mapped[int | None] = mapped_column(Integer)

    fixture_status: Mapped[str] = mapped_column(Text, nullable=False, default="scheduled")

    ht_home_score: Mapped[int | None] = mapped_column(SmallInteger)
    ht_away_score: Mapped[int | None] = mapped_column(SmallInteger)
    ft_home_score: Mapped[int | None] = mapped_column(SmallInteger)
    ft_away_score: Mapped[int | None] = mapped_column(SmallInteger)
    et_home_score: Mapped[int | None] = mapped_column(SmallInteger)
    et_away_score: Mapped[int | None] = mapped_column(SmallInteger)
    pen_home_score: Mapped[int | None] = mapped_column(SmallInteger)
    pen_away_score: Mapped[int | None] = mapped_column(SmallInteger)

    went_to_extra_time: Mapped[bool] = mapped_column(default=False)
    went_to_penalties: Mapped[bool] = mapped_column(default=False)

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

class StageGroup(Base):
    __tablename__ = "stage_group"

    group_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stage_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stage.stage_id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str | None] = mapped_column(Text)

    stage = relationship("Stage")

    __table_args__ = (
        UniqueConstraint("stage_id", "name", name="uq_stage_group_name"),
        UniqueConstraint("stage_id", "code", name="uq_stage_group_code"),
        Index("idx_stage_group_stage_id", "stage_id"),
    )

class StageGroupTeam(Base):
    __tablename__ = "stage_group_team"

    stage_group_team_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stage_group.group_id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("team.team_id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("group_id", "team_id", name="uq_stage_group_team"),
        Index("idx_sgt_group", "group_id"),
        Index("idx_sgt_team", "team_id"),
    )
