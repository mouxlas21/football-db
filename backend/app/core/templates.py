from pathlib import Path
from fastapi.templating import Jinja2Templates

BASE = Path(__file__).resolve().parents[1] 
templates = Jinja2Templates(directory=str(BASE / "templates"))
templates.env.globals.update(zip=zip, enumerate=enumerate)