from typing import Iterable, Dict
from sqlalchemy.orm import Session
from .base import BaseImporter
from .countries import CountriesImporter
from .clubs import ClubsImporter
from .competitions import CompetitionsImporter
from .players import PlayersImporter

REGISTRY: dict[str, BaseImporter] = {
    "country": CountriesImporter(),
    "countries": CountriesImporter(),
    "club": ClubsImporter(),
    "clubs": ClubsImporter(),
    "competition": CompetitionsImporter(),
    "competitions": CompetitionsImporter(),
    "player": PlayersImporter(),
    "players": PlayersImporter(),
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
