from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..db import get_db
from ..models import Competition, Country, Association, Season
from ..core.templates import templates
import unicodedata, re

router = APIRouter(prefix="/competitions", tags=["competitions"])

BASE_COMP_IMG = "/static/images/competitions"

# ---------- Country → folder slug (baked) ----------
COUNTRY_FOLDER_MAP: dict[str, str] = {
    "Afghanistan": "afghanistan", "Albania": "albania", "Algeria": "algeria",
    "American Samoa": "american-samoa", "Andorra": "andorra", "Angola": "angola",
    "Anguilla": "anguilla", "Antigua & Barbuda": "antigua-barbuda", "Argentina": "argentina",
    "Armenia": "armenia", "Aruba": "aruba", "Australia": "australia", "Austria": "austria",
    "Azerbaijan": "azerbaijan", "Bahamas": "bahamas", "Bahrain": "bahrain",
    "Bangladesh": "bangladesh", "Barbados": "barbados", "Belarus": "belarus",
    "Belgium": "belgium", "Belize": "belize", "Benin": "benin", "Bermuda": "bermuda",
    "Bhutan": "bhutan", "Bolivia": "bolivia", "Bonaire": "bonaire",
    "Bosnia & Herzegovina": "bosnia-herzegovina", "Botswana": "botswana", "Brazil": "brazil",
    "British Virgin Islands": "british-virgin-islands", "Brunei": "brunei",
    "Bulgaria": "bulgaria", "Burkina Faso": "burkina-faso", "Burundi": "burundi",
    "Cambodia": "cambodia", "Cameroon": "cameroon", "Canada": "canada",
    "Cape Verde": "cape-verde", "Cayman Islands": "cayman-islands",
    "Central African Republic": "central-african-republic", "Chad": "chad", "Chile": "chile",
    "China PR": "china-pr", "Chinese Taipei": "chinese-taipei", "Colombia": "colombia",
    "Comoros": "comoros", "Congo": "congo", "Cook Islands": "cook-islands",
    "Costa Rica": "costa-rica", "Crimea": "crimea", "Croatia": "croatia", "Cuba": "cuba",
    "Curaçao": "curacao", "Cyprus": "cyprus", "Czechia": "czechia", "Denmark": "denmark",
    "Djibouti": "djibouti", "Dominica": "dominica", "Dominican Republic": "dominican-republic",
    "DR Congo": "dr-congo", "Ecuador": "ecuador", "Egypt": "egypt", "El Salvador": "el-salvador",
    "England": "england", "Equatorial Guinea": "equatorial-guinea", "Eritrea": "eritrea",
    "Estonia": "estonia", "Eswatini": "eswatini", "Ethiopia": "ethiopia",
    "Faroe Islands": "faroe-islands", "Fiji": "fiji", "Finland": "finland", "France": "france",
    "French Guiana": "french-guiana", "Gabon": "gabon", "Georgia": "georgia", "Germany": "germany",
    "Ghana": "ghana", "Gibraltar": "gibraltar", "Greece": "greece", "Grenada": "grenada",
    "Guadeloupe": "guadeloupe", "Guam": "guam", "Guatemala": "guatemala", "Guinea": "guinea",
    "Guinea-Bissau": "guinea-bissau", "Guyana": "guyana", "Haiti": "haiti", "Honduras": "honduras",
    "Hong Kong": "hong-kong", "Hungary": "hungary", "Iceland": "iceland", "India": "india",
    "Indonesia": "indonesia", "Iran": "iran", "Iraq": "iraq", "Israel": "israel", "Italy": "italy",
    "Ivory Coast": "ivory-coast", "Jamaica": "jamaica", "Japan": "japan", "Jordan": "jordan",
    "Kazakhstan": "kazakhstan", "Kenya": "kenya", "Kiribati": "kiribati", "Kosovo": "kosovo",
    "Kuwait": "kuwait", "Kyrgyzstan": "kyrgyzstan", "Laos": "laos", "Latvia": "latvia",
    "Lebanon": "lebanon", "Lesotho": "lesotho", "Liberia": "liberia", "Libya": "libya",
    "Liechtenstein": "liechtenstein", "Lithuania": "lithuania", "Luxembourg": "luxembourg",
    "Macau": "macau", "Madagascar": "madagascar", "Malawi": "malawi", "Malaysia": "malaysia",
    "Maldives": "maldives", "Mali": "mali", "Malta": "malta", "Martinique": "martinique",
    "Mauritania": "mauritania", "Mauritius": "mauritius", "Mayotte": "mayotte", "Mexico": "mexico",
    "Micronesia": "micronesia", "Moldova": "moldova", "Monaco": "monaco", "Mongolia": "mongolia",
    "Montenegro": "montenegro", "Montserrat": "montserrat", "Morocco": "morocco",
    "Mozambique": "mozambique", "Myanmar": "myanmar", "Namibia": "namibia", "Nepal": "nepal",
    "Netherlands": "netherlands", "New Caledonia": "new-caledonia", "New Zealand": "new-zealand",
    "Nicaragua": "nicaragua", "Niger": "niger", "Nigeria": "nigeria", "North Korea": "north-korea",
    "North Macedonia": "north-macedonia", "Northern Ireland": "northern-ireland",
    "Northern Mariana": "northern-mariana-islands", "Norway": "norway", "Oman": "oman",
    "Pakistan": "pakistan", "Palestine": "palestine", "Panama": "panama",
    "Papua New Guinea": "papua-new-guinea", "Paraguay": "paraguay", "Peru": "peru",
    "Philippines": "philippines", "Poland": "poland", "Portugal": "portugal",
    "Puerto Rico": "puerto-rico", "Qatar": "qatar", "Republic of Ireland": "republic-of-ireland",
    "Réunion": "reunion", "Romania": "romania", "Russia": "russia", "Rwanda": "rwanda",
    "Saint Kitts & Nevis": "saint-kitts-nevis", "Saint Lucia": "saint-lucia",
    "Saint Pierre & Miquelon": "saint-pierre-miquelon",
    "Saint Vincent & the Grenadines": "saint-vincent-the-grenadines", "Saint-Martin": "saint-martin",
    "Samoa": "samoa", "San Marino": "san-marino", "São Tomé & Príncipe": "sao-tome-principe",
    "Saudi Arabia": "saudi-arabia", "Scotland": "scotland", "Senegal": "senegal", "Serbia": "serbia",
    "Seychelles": "seychelles", "Sierra Leone": "sierra-leone", "Singapore": "singapore",
    "Sint Maarten": "sint-maarten", "Slovakia": "slovakia", "Slovenia": "slovenia",
    "Solomon Islands": "solomon-islands", "Somalia": "somalia", "South Africa": "south-africa",
    "South Korea": "south-korea", "South Sudan": "south-sudan", "Spain": "spain",
    "Sri Lanka": "sri-lanka", "St. Barthélemy": "st-barthelemy", "Sudan": "sudan",
    "Suriname": "suriname", "Sweden": "sweden", "Switzerland": "switzerland", "Syria": "syria",
    "Tahiti": "tahiti", "Tajikistan": "tajikistan", "Tanzania": "tanzania", "Thailand": "thailand",
    "The Gambia": "gambia", "Timor-Leste": "timor-leste", "Togo": "togo", "Tonga": "tonga",
    "Trinidad & Tobago": "trinidad-tobago", "Tunisia": "tunisia", "Türkiye": "turkiye",
    "Turkmenistan": "turkmenistan", "Turks & Caicos Islands": "turks-caicos-islands",
    "Tuvalu": "tuvalu", "UAE": "uae", "Uganda": "uganda", "Ukraine": "ukraine",
    "Uruguay": "uruguay", "US Virgin Islands": "us-virgin-islands", "USA": "usa",
    "Uzbekistan": "uzbekistan", "Vanuatu": "vanuatu", "Venezuela": "venezuela",
    "Vietnam": "vietnam", "Wales": "wales", "Wallis & Futuna": "wallis-futuna", "Yemen": "yemen",
    "Zambia": "zambia", "Zanzibar": "zanzibar", "Zimbabwe": "zimbabwe",
    # historical
    "CIS": "cis", "Czechoslovakia": "czechoslovakia", "East Germany": "east-germany",
    "Soviet Union": "soviet-union", "Zaire": "zaire", "Yugoslavia": "yugoslavia", "West Germany": "west-germany",
}

# ---------- helpers ----------
def _slugify_ascii_hyphen(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()

def _image_base(country_name: Optional[str], federation_code: Optional[str]) -> Optional[str]:
    if country_name:
        folder = COUNTRY_FOLDER_MAP.get(country_name) or _slugify_ascii_hyphen(country_name)
        return f"countries/{folder}"
    if federation_code:
        return f"federations/{federation_code.lower()}"
    return None

def _federation_logo_url(fed_code: Optional[str]) -> Optional[str]:
    if not fed_code:
        return None
    return f"/static/images/associations/small/{fed_code.lower()}.png"

def _country_flag_url(country_obj: Optional[Country]) -> Optional[str]:
    if not country_obj:
        return None
    fn = getattr(country_obj, "flag_filename", None)
    if fn:
        return f"/static/images/countries/flags/small/{fn}"
    code3 = getattr(country_obj, "code_3", None) or getattr(country_obj, "iso3", None) or getattr(country_obj, "alpha3", None)
    if code3:
        return f"/static/images/countries/flags/small/{code3.lower()}.png"
    slug = COUNTRY_FOLDER_MAP.get(country_obj.name)
    if slug:
        return f"/static/images/competitions/countries/{slug}/thumbs/{slug}.png"
    return None

# ---------- sorting utilities ----------
_CUP_ORDER = {
    "national cup": 0,
    "league cup": 1,
    "super cup": 2,
    "domestic cup": 3,
    "state cup": 4,
    "amateur cup": 5,
    "commemorative": 6,
}
def _cup_rank_priority(s: Optional[str]) -> int:
    return _CUP_ORDER.get((s or "").strip().lower(), 999)

def _gender_priority(s: Optional[str]) -> int:
    v = (s or "").strip().lower()
    if v in ("m", "men", "male"): return 0
    if v in ("w", "women", "female"): return 1
    return 2

def _age_priority(s: Optional[str]) -> int:
    v = (s or "").strip().lower()
    if v in ("senior", "open"): return 0
    if v in ("youth", "u23", "u21", "u20", "u19", "u18", "u17", "u16", "u15"): return 1
    return 2

def _type_priority(t: Optional[str]) -> int:
    v = (t or "").strip().lower()
    if v == "league": return 0
    if v == "cup": return 1
    return 2  # qualifiers/other

def _domestic_bucket(x: Dict[str, Any]) -> int:
    """
    0 = Clubs, 1 = National Teams, 2 = Qualifiers
    Clubs if cup_rank says clubs/club OR type == league.
    National Teams if cup_rank says NT.
    Qualifiers if type is qualifier(s)/qualification.
    """
    t = (x.get("type") or "").strip().lower()
    cr = (x.get("cup_rank") or "").strip().lower()
    if t in ("qualifier", "qualifiers", "qualification"):
        return 2
    if cr in ("national teams", "national_team", "national-teams", "nt"):
        return 1
    if cr in ("clubs", "club") or t == "league":
        return 0
    return 0

def _league_metric(x: Dict[str, Any]) -> int:
    try:
        return int(x.get("tier")) if x.get("tier") is not None else 9999
    except Exception:
        return 9999

def _cup_metric(x: Dict[str, Any]) -> int:
    return _cup_rank_priority(x.get("cup_rank"))

def _domestic_sort_key(x: Dict[str, Any]):
    # men→women→unknown; within each: senior→youth→unknown
    gpri = _gender_priority(x.get("gender"))
    apri = _age_priority(x.get("age_group"))
    bucket = _domestic_bucket(x)
    tpri = _type_priority(x.get("type"))
    metric = _league_metric(x) if (x.get("type") or "").lower() == "league" else (_cup_metric(x) if (x.get("type") or "").lower() == "cup" else 9999)
    return (gpri, apri, bucket, tpri, metric, x.get("name") or "")

# *** NEW: International sort matches the domestic logic ***
def _international_sort_key(x: Dict[str, Any]):
    gpri = _gender_priority(x.get("gender"))
    apri = _age_priority(x.get("age_group"))
    bucket = _domestic_bucket(x)   # same bucket logic works for internationals
    tpri = _type_priority(x.get("type"))
    metric = _league_metric(x) if (x.get("type") or "").lower() == "league" else (_cup_metric(x) if (x.get("type") or "").lower() == "cup" else 9999)
    return (gpri, apri, bucket, tpri, metric, x.get("name") or "")

# ---------- pages ----------
@router.get("", response_class=HTMLResponse)
def competitions_page(request: Request, db: Session = Depends(get_db)):
    comps: List[Competition] = db.execute(select(Competition).order_by(Competition.name)).scalars().all()

    # lookups
    country_ids = {c.country_id for c in comps if c.country_id}
    countries: Dict[int, Country] = {}
    if country_ids:
        res = db.execute(select(Country).where(Country.country_id.in_(country_ids))).scalars().all()
        countries = {c.country_id: c for c in res}

    ass_ids = {c.organizer_ass_id for c in comps if c.organizer_ass_id}
    assocs: Dict[int, Association] = {}
    if ass_ids:
        res = db.execute(select(Association).where(Association.ass_id.in_(ass_ids))).scalars().all()
        assocs = {a.ass_id: a for a in res}

    # federation grouping
    fed_groups: Dict[str, Dict[str, Any]] = {}
    for c in comps:
        assoc = assocs.get(c.organizer_ass_id) if c.organizer_ass_id else None
        fed_code = (assoc.code if assoc else "UNKNOWN").upper()
        fed_name = assoc.name if assoc else "Unknown"
        fg = fed_groups.setdefault(fed_code, {
            "code": fed_code,
            "code_l": fed_code.lower(),
            "name": fed_name,
            "logo": _federation_logo_url(fed_code),
            "international": [],
            "domestic_by_country": {}
        })

        country_obj = countries.get(c.country_id) if c.country_id else None
        country_name = country_obj.name if country_obj else None
        img_base = _image_base(country_name, fed_code)

        vm = {
            "id": c.competition_id,
            "name": c.name,
            "type": c.type,
            "tier": c.tier,
            "cup_rank": c.cup_rank,
            "gender": c.gender,
            "age_group": c.age_group,
            "status": c.status,
            "filename": c.logo_filename,
            "image_base": img_base,
            "country_name": country_name,
            "organizer_code": fed_code,
        }

        if country_name:
            cslug = COUNTRY_FOLDER_MAP.get(country_name) or _slugify_ascii_hyphen(country_name)
            bucket = fg["domestic_by_country"].setdefault(country_name, {
                "country": {
                    "name": country_name,
                    "slug": cslug,
                    "flag": _country_flag_url(country_obj),
                },
                "items": []
            })
            bucket["items"].append(vm)
        else:
            fg["international"].append(vm)

    # sort
    for fg in fed_groups.values():
        # International now has the same priority stack as domestic
        fg["international"].sort(key=_international_sort_key)

        domestic = list(fg["domestic_by_country"].values())
        for grp in domestic:
            grp["items"].sort(key=_domestic_sort_key)
        fg["domestic"] = sorted(domestic, key=lambda g: g["country"]["name"])
        del fg["domestic_by_country"]

    federations = list(fed_groups.values())
    federations.sort(key=lambda g: (0 if g["code"] == "FIFA" else 1, g["name"]))

    return templates.TemplateResponse(
        "competitions.html",
        {"request": request, "federations": federations, "BASE_COMP_IMG": BASE_COMP_IMG},
    )

@router.get("/{competition_id}", response_class=HTMLResponse)
def competition_detail_page(competition_id: int, request: Request, db: Session = Depends(get_db)):
    comp = db.execute(select(Competition).where(Competition.competition_id == competition_id)).scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Competition not found")

    country = db.execute(select(Country).where(Country.country_id == comp.country_id)).scalar_one_or_none() if comp.country_id else None
    organizer = db.execute(select(Association).where(Association.ass_id == comp.organizer_ass_id)).scalar_one_or_none() if comp.organizer_ass_id else None
    seasons = db.execute(select(Season).where(Season.competition_id == comp.competition_id)).scalars().all()

    # Paths & assets
    country_name = country.name if country else None
    assoc_code = organizer.code if organizer else None
    image_base = _image_base(country_name, assoc_code)
    country_flag_url = _country_flag_url(country) if country else None
    organizer_logo_url = _federation_logo_url(assoc_code) if assoc_code else None

    # Sorting seasons (DESC by label; supports .season_name or .name)
    def _season_label(s):
        return getattr(s, "season_name", None) or getattr(s, "name", "") or ""

    seasons_sorted = sorted(seasons, key=_season_label, reverse=True)
    current_season_label = _season_label(seasons_sorted[0]) if seasons_sorted else None

    return templates.TemplateResponse(
        "competition_detail.html",
        {
            "request": request,
            "competition": comp,
            "country": country,
            "organizer": organizer,
            "seasons": seasons,  # original (optional)
            "seasons_sorted": seasons_sorted,
            "current_season_label": current_season_label,
            "image_base": image_base,
            "filename": comp.logo_filename,
            "BASE_COMP_IMG": BASE_COMP_IMG,
            "country_flag_url": country_flag_url,
            "organizer_logo_url": organizer_logo_url,
        },
    )

