from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..db import get_db
from ..models import Association
from ..core.templates import templates

router = APIRouter(prefix="/associations", tags=["associations"])

@router.get("", response_class=HTMLResponse)
def associations_page(request: Request, q: str | None = Query(None), db: Session = Depends(get_db)):
    stmt = select(Association)
    if q:
        stmt = stmt.where(Association.name.ilike(f"%{q}%") | Association.code.ilike(f"%{q}%"))
    rows = db.execute(stmt.order_by(Association.level, Association.code)).scalars().all()
    return templates.TemplateResponse("associations.html", {"request": request, "rows": rows, "q": q or ""})

@router.get("/{ass_id}", response_class=HTMLResponse)
def association_detail(ass_id: int, request: Request, db: Session = Depends(get_db)):
    a = db.execute(select(Association).where(Association.ass_id == ass_id)).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Association not found")
    parent = None
    if a.parent_org_id:
        parent = db.execute(select(Association).where(Association.ass_id == a.parent_org_id)).scalar_one_or_none()
    children = db.execute(select(Association).where(Association.parent_org_id == a.ass_id)).scalars().all()
    return templates.TemplateResponse("association_detail.html", {"request": request, "a": a, "parent": parent, "children": children})
