from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional
from fastapi.templating import Jinja2Templates

# Base paths
BASE = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = BASE / "templates"
STATIC_DIR = BASE / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals.update(zip=zip, enumerate=enumerate)

# ---- Internal helpers --------------------------------------------------------

Size = Literal["normal", "small", "big"]
Kind = Literal[
    "association",      # images/associations/{,small/,big/}<file>
    "competition",      # images/competitions/{,small/,big/}<file>
    "club",             # images/clubs/{,small/,big/}<file>
    "country_flag",     # images/countries/flags/{,small/}<file>
    "team",             # images/countries/teams/<file>
    "stadium",          # images/stadiums/<file>
]

def _join(*parts: str) -> str:
    return "/".join(p.strip("/\\") for p in parts if p)

def _with_cache_bust(rel_path: str) -> str:
    """
    Turn a static-relative path like 'images/clubs/small/foo.png'
    into '/static/images/clubs/small/foo.png?v=<mtime>' if the file exists.
    """
    fs_path = STATIC_DIR / rel_path
    if fs_path.exists():
        try:
            mtime = int(fs_path.stat().st_mtime)
            return "/" + _join("static", rel_path) + f"?v={mtime}"
        except OSError:
            pass
    return "/" + _join("static", rel_path)

def _folder_for(kind: Kind, size: Size) -> str:
    if kind == "association":
        return _join("images", "associations", "" if size == "normal" else size)
    if kind == "competition":
        return _join("images", "competitions", "" if size == "normal" else size)
    if kind == "club":
        return _join("images", "clubs", "" if size == "normal" else size)
    if kind == "country_flag":
        # only normal or small in your tree; ignore 'big'
        sub = "" if size in ("normal", "big") else "small"
        return _join("images", "countries", "flags", sub)
    if kind == "team":
        # no size variants in your tree for teams
        return _join("images", "countries", "teams")
    if kind == "stadium":
        # no size variants in your tree for stadiums
        return _join("images", "stadiums")
    raise ValueError(f"Unknown kind: {kind}")

def _image_url(kind: Kind, filename: Optional[str], size: Size = "normal", default_rel: Optional[str] = None) -> Optional[str]:
    """
    Build a size-aware static URL for the given entity kind and filename.
    Returns None if filename is falsy and no default is provided.
    """
    if filename:
        rel = _join(_folder_for(kind, size), filename)
        return _with_cache_bust(rel)
    if default_rel:
        return _with_cache_bust(default_rel.lstrip("/"))
    return None

# ---- Public helpers exposed to Jinja ----------------------------------------

def association_logo_url(filename: Optional[str], size: Size = "normal") -> Optional[str]:
    return _image_url("association", filename, size)

def competition_logo_url(filename: Optional[str], size: Size = "normal") -> Optional[str]:
    return _image_url("competition", filename, size)

def club_logo_url(filename: Optional[str], size: Size = "normal") -> Optional[str]:
    return _image_url("club", filename, size)

def flag_url(filename: Optional[str], size: Size = "normal") -> Optional[str]:
    # size supports 'normal' or 'small' (big maps to normal)
    return _image_url("country_flag", filename, size)

def team_logo_url(filename: Optional[str]) -> Optional[str]:
    # teams have no size variants in your tree
    return _image_url("team", filename, "normal")

def stadium_photo_url(filename: Optional[str]) -> Optional[str]:
    # stadiums have no size variants in your tree
    return _image_url("stadium", filename, "normal")

def static_url(rel_path: str) -> str:
    """
    Generic static URL with cache-busting (e.g., CSS/JS).
    rel_path: path relative to 'backend/app/static', like 'css/main.css'
    """
    return _with_cache_bust(rel_path)

# Register globals for Jinja templates (usable directly in HTML)
templates.env.globals.update(
    association_logo_url=association_logo_url,
    competition_logo_url=competition_logo_url,
    club_logo_url=club_logo_url,
    flag_url=flag_url,
    team_logo_url=team_logo_url,
    stadium_photo_url=stadium_photo_url,
    static_url=static_url,
)
