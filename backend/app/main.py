import csv
from fastapi import FastAPI, Depends, HTTPException, Request, File, UploadFile, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select
from .db import get_db
from .schemas import CountryCreate, CountryRead, LeagueCreate, LeagueRead
from io import TextIOWrapper
from .models import Country, League


app = FastAPI(title="Football DB API")

# --- NEW: Static & Templates ---
# Ensure these folders exist: app/static and app/templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# --- Home (Hybrid: dashboard + classic index) ---
@app.get("/", response_class=HTMLResponse)
def home(request: Request, season: str | None = None):
    # The widgets are loaded client-side from /api/* endpoints
    return templates.TemplateResponse("index.html", {
        "request": request,
        "season": season or "",
    })



# --- HTML: Countries list page ---
@app.get("/countries", response_class=HTMLResponse)
def countries_page(
    request: Request,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Country)
    if q:
        q_like = f"%{q.strip()}%"
        stmt = stmt.where(Country.name.ilike(q_like))
    rows = db.execute(stmt.order_by(Country.name)).scalars().all()
    return templates.TemplateResponse(
        "countries.html",
        {
            "request": request,
            "countries": rows,
            "q": q or "",
        },
    )

# --- HTML: very simple country detail page stub, linked from the table
@app.get("/countries/{country_id}", response_class=HTMLResponse)
def country_detail_page(
    country_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    country = db.execute(select(Country).where(Country.country_id == country_id)).scalar_one_or_none()
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")

    leagues = db.execute(
        select(League).where(League.country_id == country_id).order_by(League.tier.nulls_last(), League.name)
    ).scalars().all()

    # TODO (future): cups, supercups, league cups, etc., when you add those tables
    cups = []  # placeholder

    return templates.TemplateResponse(
        "country_detail.html",
        {"request": request, "country": country, "leagues": leagues, "cups": cups},
    )

# --- HTML: Leagues list page ---
@app.get("/leagues", response_class=HTMLResponse)
def leagues_page(
    request: Request,
    q: str | None = None,
    country_id: int | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(League)
    if q:
        q_like = f"%{q.strip()}%"
        stmt = stmt.where(League.name.ilike(q_like))
    if country_id:
        stmt = stmt.where(League.country_id == country_id)

    rows = db.execute(
        stmt.order_by(League.tier.nulls_last(), League.name)
    ).scalars().all()

    # country map for pretty display (id -> name)
    countries = db.execute(select(Country.country_id, Country.name)).all()
    country_map = {cid: cname for cid, cname in countries}

    return templates.TemplateResponse(
        "leagues.html",
        {"request": request, "leagues": rows, "q": q or "", "country_id": country_id, "country_map": country_map},
    )

# --- HTML: League detail page ---
@app.get("/leagues/{league_id}", response_class=HTMLResponse)
def league_detail_page(
    league_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    league = db.execute(select(League).where(League.league_id == league_id)).scalar_one_or_none()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    # pull its country for linking
    country = db.execute(select(Country).where(Country.country_id == league.country_id)).scalar_one_or_none()

    return templates.TemplateResponse(
        "league_detail.html",
        {"request": request, "league": league, "country": country},
    )



# --- API: Countries ---
@app.get("/api/countries", response_model=list[CountryRead])
def list_countries(db: Session = Depends(get_db)):
    rows = db.execute(select(Country).order_by(Country.name)).scalars().all()
    return [CountryRead(country_id=r.country_id, name=r.name, iso2=r.iso2) for r in rows]

@app.post("/api/countries", response_model=CountryRead)
def create_country(payload: CountryCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    iso2 = payload.iso2.upper() if payload.iso2 else None
    exists = db.execute(select(Country).where(Country.name.ilike(name))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="Country already exists")
    row = Country(name=name, iso2=iso2)
    db.add(row)
    db.commit()
    db.refresh(row)
    return CountryRead(country_id=row.country_id, name=row.name, iso2=row.iso2)

# --- API: Leagues ---
@app.get("/api/leagues", response_model=list[LeagueRead])
def list_leagues(
    country_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    stmt = select(League)
    if country_id:
        stmt = stmt.where(League.country_id == country_id)
    rows = db.execute(stmt.order_by(League.tier.nulls_last(), League.name).limit(limit)).scalars().all()
    return [LeagueRead.model_validate(r) for r in rows]

@app.get("/api/leagues/{league_id}", response_model=LeagueRead)
def get_league(league_id: int, db: Session = Depends(get_db)):
    row = db.execute(select(League).where(League.league_id == league_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="League not found")
    return LeagueRead.model_validate(row)

@app.post("/api/leagues", response_model=LeagueRead)
def create_league(payload: LeagueCreate, db: Session = Depends(get_db)):
    exists = db.execute(select(League).where(League.name.ilike(payload.name.strip()))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="League already exists")
    row = League(
        name=payload.name.strip(),
        slug=(payload.slug or None),
        tier=payload.tier,
        country_id=payload.country_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return LeagueRead.model_validate(row)

# --- Minimal CSV import page (unchanged) ---
@app.get("/import", response_class=HTMLResponse)
def import_page():
    return """
<!doctype html>
<html><head><meta charset="utf-8"><title>CSV Import</title></head>
<body style="font-family:system-ui;max-width:760px;margin:2rem auto">
  <h1>CSV Import</h1>
  <p>Select entity and upload a CSV file.</p>
  <ul>
    <li><b>country</b> — columns: <code>name</code>, <code>iso2</code> (optional)</li>
    <li><b>league</b> — columns: <code>name</code>, <code>country_iso2</code>, <code>tier</code> (optional), <code>slug</code> (optional)</li>
  </ul>

  <form id="imp" onsubmit="send(event)" style="margin-top:1rem">
    <label>Entity:
      <select name="entity">
        <option value="country">country</option>
        <option value="league">league</option>
      </select>
    </label>
    <input type="file" name="file" accept=".csv" required>
    <button>Upload</button>
  </form>
  <pre id="out" style="background:#111;color:#eee;padding:12px;border-radius:8px;min-height:4rem"></pre>

<script>
async function send(ev){
  ev.preventDefault();
  const form = document.getElementById('imp');
  const fd = new FormData(form);
  const entity = fd.get('entity');
  const r = await fetch('/api/import/csv?entity='+encodeURIComponent(entity), { method:'POST', body: fd });
  const txt = await r.text();
  document.getElementById('out').textContent = txt;
}
</script>
</body></html>
"""

@app.post("/api/import/csv")
async def import_csv(entity: str = Query(..., min_length=2),
                     file: UploadFile = File(...),
                     db: Session = Depends(get_db)):
    entity = entity.strip().lower()

    if file.content_type not in ("text/csv", "application/vnd.ms-excel", "application/csv"):
        return {"status": "error", "detail": f"Unsupported content_type: {file.content_type}"}

    text = TextIOWrapper(file.file, encoding="utf-8", errors="replace")
    reader = csv.DictReader(text)
    if not reader.fieldnames:
        return {"status": "error", "detail": "CSV has no header row"}

    headers = {h.strip().lower(): h for h in reader.fieldnames}

    # --- Country import ---
    if entity == "country":
        required = {"name"}
        missing = required - set(headers.keys())
        if missing:
            return {"status": "error", "detail": f"Missing required column(s): {sorted(missing)}"}

        added = skipped = 0
        for row in reader:
            name = (row.get(headers["name"]) or "").strip()
            iso2 = (row.get(headers.get("iso2", "iso2")) or "").strip().upper() or None
            if not name:
                continue
            stmt = insert(Country).values(name=name, iso2=iso2).on_conflict_do_nothing()
            result = db.execute(stmt)
            added += 1 if result.rowcount == 1 else 0
            skipped += 0 if result.rowcount == 1 else 1

        db.commit()
        return {"status": "ok", "entity": "country", "added": added, "skipped_duplicates": skipped}

    # --- League import ---
    if entity == "league":
        required = {"name", "country_iso2"}
        missing = required - set(headers.keys())
        if missing:
            return {"status": "error", "detail": f"Missing required column(s): {sorted(missing)}"}

        # Build iso2 -> country_id map once
        iso2_to_id = {
            c.iso2.upper(): c.country_id
            for c in db.execute(select(Country)).scalars().all()
            if c.iso2
        }

        added = skipped = 0
        for row in reader:
            name = (row.get(headers["name"]) or "").strip()
            iso2 = (row.get(headers["country_iso2"]) or "").strip().upper()
            tier = row.get(headers.get("tier", "tier"))
            slug = (row.get(headers.get("slug", "slug")) or "").strip() or None

            if not name or not iso2:
                continue

            country_id = iso2_to_id.get(iso2)
            if not country_id:
                # country missing – skip this row
                skipped += 1
                continue

            # avoid duplicates by league name
            existing = db.execute(select(League).where(League.name.ilike(name))).scalar_one_or_none()
            if existing:
                skipped += 1
                continue

            db.add(League(
                name=name,
                slug=slug,
                tier=int(tier) if (tier and str(tier).isdigit()) else None,
                country_id=country_id,
            ))
            added += 1

        db.commit()
        return {"status": "ok", "entity": "league", "added": added, "skipped": skipped}

    # --- Fallback ---
    return {"status": "error", "detail": f"Unsupported entity: {entity}"}