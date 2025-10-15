from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .routers import associations, countries, clubs, competitions, fixtures, leagues, cups, players, imports, admin_import, stadiums, confederations
from .core.templates import templates

app = FastAPI(title="Football DB (Original Schema)")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(associations.router)
app.include_router(countries.router)
app.include_router(stadiums.router)
app.include_router(clubs.router)
app.include_router(competitions.router)
app.include_router(players.router)
app.include_router(fixtures.router)
app.include_router(imports.router)
app.include_router(leagues.router)
app.include_router(cups.router)
app.include_router(admin_import.router)
app.include_router(confederations.router)
#app.include_router(reference.router)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
