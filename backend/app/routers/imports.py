from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
import csv
from io import TextIOWrapper

from ..db import get_db
from ..core.templates import templates
from ..services.importers import import_rows, get_importer

router = APIRouter(prefix="/import", tags=["import"])

@router.get("", response_class=HTMLResponse)
def import_page(request: Request):
    return templates.TemplateResponse("import.html", {"request": request})

@router.post("/csv")
async def import_csv(
    request: Request,
    entity: str = Query(..., regex="^(country|countries|club|clubs|competition|competitions|player|players|stadium|stadiums|season|seasons|stage|stages|stage_round|stage_rounds|stage_group|stage_groups|team|teams|fixture|fixtures|association|associations)$"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        get_importer(entity)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        wrapper = TextIOWrapper(file.file, encoding="utf-8")
        reader = csv.DictReader(wrapper)
        rows = list(reader)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {e}")

    if not rows:
        return JSONResponse({"inserted": 0, "skipped": 0, "errors": [], "entity": entity, "message": "No data"}, 200)

    try:
        result = import_rows(entity, rows, db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Import failed: {e}")

    return result
