from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Iterable, Tuple
from sqlalchemy.orm import Session

@dataclass
class ImportResult:
    inserted: int = 0
    skipped: int = 0
    errors: list[str] | None = None

    def as_dict(self) -> dict:
        return {"inserted": self.inserted, "skipped": self.skipped, "errors": self.errors or []}

class BaseImporter:
    entity: str

    def import_rows(self, rows: Iterable[Dict[str, Any]], db: Session) -> ImportResult:
        res = ImportResult(inserted=0, skipped=0, errors=[])
        for i, raw in enumerate(rows, start=1):
            try:
                ok, model_kwargs = self.parse_row(raw, db)
                if not ok:
                    res.skipped += 1
                    continue
                if self.upsert(model_kwargs, db):
                    res.inserted += 1
            except Exception as e:
                res.skipped += 1
                res.errors.append(f"Row {i}: {e}")
        db.commit()
        return res

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        raise NotImplementedError

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        raise NotImplementedError
