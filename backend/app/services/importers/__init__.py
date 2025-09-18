# backend/app/services/importers/__init__.py
from typing import Iterable, Dict
from sqlalchemy.orm import Session
from .base import BaseImporter
from .associations import AssociationsImporter
from .countries import CountriesImporter
from .stadiums import StadiumsImporter
from .competitions import CompetitionsImporter
from .clubs import ClubsImporter
from .teams import TeamsImporter
from .seasons import SeasonsImporter
from .stages import StagesImporter
from .stage_rounds import StageRoundsImporter 
from .stage_groups import StageGroupsImporter
from .stage_group_teams import StageGroupTeamsImporter
from .players import PlayersImporter
from .coaches import CoachesImporter
from .officials import OfficialsImporter
from .fixtures import FixturesImporter




REGISTRY: dict[str, BaseImporter] = {
    "association": AssociationsImporter(),
    "associations": AssociationsImporter(),
    "country": CountriesImporter(),
    "countries": CountriesImporter(),
    "stadium": StadiumsImporter(),
    "stadiums": StadiumsImporter(),
    "competition": CompetitionsImporter(),
    "competitions": CompetitionsImporter(),
    "club": ClubsImporter(),
    "clubs": ClubsImporter(),
    "team": TeamsImporter(),
    "teams": TeamsImporter(),
    "season": SeasonsImporter(),
    "seasons": SeasonsImporter(),
    "stage": StagesImporter(),
    "stages": StagesImporter(),
    "stage_round": StageRoundsImporter(),
    "stage_rounds": StageRoundsImporter(),
    "stage_group": StageGroupsImporter(),
    "stage_groups": StageGroupsImporter(),
    "stage_group_team": StageGroupTeamsImporter(),
    "stage_group_teams": StageGroupTeamsImporter(),
    "player": PlayersImporter(),
    "players": PlayersImporter(),
    "coache": CoachesImporter(),
    "coaches": CoachesImporter(),
    "official": OfficialsImporter(),
    "officials": OfficialsImporter(),
    "fixture": FixturesImporter(),
    "fixtures": FixturesImporter(),
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
