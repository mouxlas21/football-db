from sqlalchemy import BigInteger, Integer, Text, CHAR, Column, String, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class Country(Base):
    __tablename__ = "country"
    country_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    iso2: Mapped[str | None] = mapped_column(CHAR(2), unique=True, nullable=True)

class League(Base):
    __tablename__ = "league"
    league_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False, unique=True)
    slug = Column(String(160), nullable=True, unique=True)
    tier = Column(Integer, nullable=True)  # 1 for top division, etc.
    country_id = Column(Integer, ForeignKey("country.country_id", ondelete="RESTRICT"), nullable=False)

    country = relationship("Country", backref="leagues")

Index("ix_league_country", League.country_id)
