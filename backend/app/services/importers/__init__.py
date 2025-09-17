# backend/app/services/importers/__init__.py
from typing import Iterable, Dict
from sqlalchemy.orm import Session
from .base import BaseImporter
from .associations import AssociationsImporter
from .countries import CountriesImporter
from .clubs import ClubsImporter
from .competitions import CompetitionsImporter
from .players import PlayersImporter
from .fixtures import FixturesImporter
from .stadiums import StadiumsImporter
from .seasons import SeasonsImporter
from .stages import StagesImporter
from .stage_rounds import StageRoundsImporter  # <-- renamed
from .teams import TeamsImporter

REGISTRY: dict[str, BaseImporter] = {
    "association": AssociationsImporter(),
    "associations": AssociationsImporter(),
    "country": CountriesImporter(),
    "countries": CountriesImporter(),
    "club": ClubsImporter(),
    "clubs": ClubsImporter(),
    "competition": CompetitionsImporter(),
    "competitions": CompetitionsImporter(),
    "player": PlayersImporter(),
    "players": PlayersImporter(),
    "fixture": FixturesImporter(),
    "fixtures": FixturesImporter(),
    "stadium": StadiumsImporter(),
    "stadiums": StadiumsImporter(),
    "season": SeasonsImporter(),
    "seasons": SeasonsImporter(),
    "stage": StagesImporter(),
    "stages": StagesImporter(),
    "stage_round": StageRoundsImporter(),
    "stage_rounds": StageRoundsImporter(),
    "team": TeamsImporter(),
    "teams": TeamsImporter(),
}

def get_importer(entity: str) -> BaseImporter:
    key = (entity or "").lower().strip()
    if key not in REGISTRY:
        raise KeyError(f"Unsupported entity: {entity}")
    return REGISTRY[key]

def import_rows(entity: str, rows: Iterable[Dict], db: Session) -> dict:
    importer = get_importer(entity)
    result = importer.import_rows(rows, db)
    out = result.as_dict()
    out["entity"] = entity
    return out
