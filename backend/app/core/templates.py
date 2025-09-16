# backend/app/core/templates.py
from pathlib import Path
from fastapi.templating import Jinja2Templates

BASE = Path(__file__).resolve().parents[1]  # points to backend/app
templates = Jinja2Templates(directory=str(BASE / "templates"))
