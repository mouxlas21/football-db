from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text
from sqlalchemy.dialects.postgresql import insert
from .base import BaseImporter
from app.models import Season, Competition
from .utils.helpers import _to_int, _parse_date

class SeasonsImporter(BaseImporter):
    entity = "seasons"

    def _resolve_competition_id(self, token: str | None, db: Session) -> int | None:
        """
        Accepts:
          - numeric id (e.g., "1")
          - competition name (case-insensitive exact): "Bundesliga", "FA Cup"
        """
        if token is None:
            return None

        # Try as integer id
        as_int = _to_int(token)
        if as_int is not None:
            return as_int

        # Else try by name (case-insensitive exact)
        name = str(token).strip()
        if not name:
            return None
        row = db.execute(
            select(Competition).where(func.lower(Competition.name) == func.lower(name))
        ).scalar_one_or_none()
        return row.competition_id if row else None

    def parse_row(self, raw: Dict[str, Any], db: Session) -> Tuple[bool, Dict[str, Any]]:
        name = (raw.pop("name", None) or "").strip()
        if not name:
            return False, {}

        comp_token = (
            raw.pop("competition_id", None)
            or raw.pop("competition_name", None)
            or raw.pop("competition", None)
        )
        competition_id = self._resolve_competition_id(comp_token, db)
        if not competition_id:
            return False, {}

        start_date = _parse_date(raw.pop("start_date", None))
        end_date = _parse_date(raw.pop("end_date", None))

        ### points rule (either "points_rule" like "2-1-0" OR explicit columns)
        pr = (raw.pop("points_rule", None) or "").strip()
        if pr:
            try:
                w, d, l = (int(x) for x in pr.split("-", 2))
            except Exception:
                w, d, l = 3, 1, 0
        else:
            w = _to_int(raw.pop("win_points", None))  or 3
            d = _to_int(raw.pop("draw_points", None)) or 1
            l = _to_int(raw.pop("loss_points", None)) or 0

        return True, {
            "competition_id": competition_id,
            "name": name,
            "start_date": start_date,
            "end_date": end_date,
            "win_points": w,   # carry through to upsert
            "draw_points": d,
            "loss_points": l,
        }

    def upsert(self, kwargs: Dict[str, Any], db: Session) -> bool:
        # unique (competition_id, name)
        existing = db.execute(
            select(Season).where(
                Season.competition_id == kwargs["competition_id"],
                Season.name == kwargs["name"],
            )
        ).scalar_one_or_none()

        # Keep start/end updates
        if existing:
            changed = False
            for f in ("start_date", "end_date"):
                v = kwargs.get(f)
                if v is not None and getattr(existing, f) != v:
                    setattr(existing, f, v)
                    changed = True
            db.flush() if changed else None
            season_id = existing.season_id
            created = False
        else:
            res = db.execute(insert(Season).values(
                competition_id=kwargs["competition_id"],
                name=kwargs["name"],
                start_date=kwargs.get("start_date"),
                end_date=kwargs.get("end_date"),
            ).returning(Season.season_id))
            season_id = res.scalar_one()
            created = True

        # Write rule only if non-default (avoid clutter)
        w, d, l = kwargs.get("win_points", 3), kwargs.get("draw_points", 1), kwargs.get("loss_points", 0)
        if (w, d, l) != (3, 1, 0):
            db.execute(text("""
                INSERT INTO season_points_rule (season_id, win_points, draw_points, loss_points)
                VALUES (:sid, :w, :d, :l)
                ON CONFLICT (season_id) DO UPDATE
                SET win_points = EXCLUDED.win_points,
                    draw_points = EXCLUDED.draw_points,
                    loss_points = EXCLUDED.loss_points
            """), {"sid": season_id, "w": w, "d": d, "l": l})

        return created