from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .routers import associations, countries, clubs, competitions, fixtures, players, imports
from .core.templates import templates

app = FastAPI(title="Football DB (Original Schema)")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(associations.router)
app.include_router(countries.router)
app.include_router(clubs.router)
app.include_router(competitions.router)
app.include_router(players.router)
app.include_router(fixtures.router)
app.include_router(imports.router)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
