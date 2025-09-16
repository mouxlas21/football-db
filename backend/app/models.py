from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    Text,
    Date,
    SmallInteger,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .db import Base
from datetime import date

class Country(Base):
    __tablename__ = "country"

    country_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    iso2: Mapped[str | None] = mapped_column(String(2), unique=True)


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
    organizer: Mapped[str | None] = mapped_column(Text)
    country_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("country.country_id", ondelete="SET NULL"))
    confederation: Mapped[str | None] = mapped_column(Text)

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