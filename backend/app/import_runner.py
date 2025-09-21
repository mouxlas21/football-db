import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests

# ---------- Config ----------
DEFAULT_BASE_URL = os.getenv("IMPORT_BASE_URL", "http://localhost:8000")
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
MANIFEST_PATH = os.getenv("IMPORT_MANIFEST", str(Path(DATA_DIR) / "import_manifest.json"))

# Phase ordering (lower means earlier)
ENTITY_PHASE_ORDER = {
    # Phase A – bases
    "association": 10,
    "country": 20,
    "stadium": 30,
    "competition": 40,
    "club": 50,
    "team": 60,

    # Phase A.5 – people (moved earlier per request)
    "person": 70,
    "player": 80,
    "coach": 85,
    "official": 90,

    # Phase B – season & structure
    "season": 100,
    "league_points_adjustment": 110,
    "league_table_snapshot": 120,
    "stage": 130,
    "stage_round": 140,
    "stage_group": 150,
    "stage_group_team": 160,

    # Phase C – fixtures
    "fixture": 200,

    # Phase D – match data
    "lineup": 400,
    "appearance": 410,
    "substitution": 420,
    "event": 430,
    "team_match_stats": 440,
    "player_match_stats": 450,
    "table_standings": 460,
}

# Filename → entity patterns (fallback when no manifest override)
PATTERNS = [
    (r"(^|/)associations\.csv$", "association"),
    (r"(^|/)countries.*\.csv$", "country"),
    (r"(^|/)stadiums.*\.csv$", "stadium"),
    (r"(^|/)competitions.*\.csv$", "competition"),
    (r"(^|/)clubs.*\.csv$", "club"),
    (r"(^|/)teams.*\.csv$", "team"),

    (r"(^|/).+_season\.csv$", "season"),
    (r"(^|/).+_stages\.csv$", "stage"),
    (r"(^|/).+_stage_rounds\.csv$", "stage_round"),
    (r"(^|/).+_stage_groups\.csv$", "stage_group"),
    (r"(^|/).+_stage_group_teams\.csv$", "stage_group_team"),

    (r"(^|/).+_fixtures\.csv$", "fixture"),

    (r"(^|/)person.*\.csv$", "person"),
    (r"(^|/)players.*\.csv$", "player"),
    (r"(^|/)coaches.*\.csv$", "coach"),
    (r"(^|/)officials.*\.csv$", "official"),

    (r"(^|/)lineups.*\.csv$", "lineup"),
    (r"(^|/)appearances.*\.csv$", "appearance"),
    (r"(^|/)substitutions.*\.csv$", "substitution"),
    (r"(^|/)events.*\.csv$", "event"),
    (r"(^|/)team_match_stats.*\.csv$", "team_match_stats"),
    (r"(^|/)player_match_stats.*\.csv$", "player_match_stats"),
    (r"(^|/)table_standings.*\.csv$", "table_standings"),
]

def infer_entity(path: str) -> str | None:
    p = path.replace("\\", "/")
    for pat, ent in PATTERNS:
        if re.search(pat, p, flags=re.IGNORECASE):
            return ent
    return None

def load_manifest(manifest_path: str):
    if not os.path.isfile(manifest_path):
        return None
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)
    return m

def discover_csvs(root: str, pack: str | None = None):
    root_path = Path(root)
    if pack:
        search_root = root_path / "packs" / pack
    else:
        search_root = root_path
    return sorted([str(p) for p in search_root.rglob("*.csv")])

def classify_files(files: list[str], manifest: dict | None):
    classified = []
    override_map = {}
    if manifest and "overrides" in manifest:
        for ov in manifest["overrides"]:
            override_map[os.path.normpath(ov["file"])] = ov["entity"]

    for f in files:
        nf = os.path.normpath(f)
        entity = override_map.get(nf) or infer_entity(nf)
        if not entity:
            print(f"[skip] Unrecognized CSV (no entity match): {f}")
            continue
        order = ENTITY_PHASE_ORDER.get(entity, 9999)
        classified.append({"path": nf, "entity": entity, "order": order})
    classified.sort(key=lambda x: (x["order"], x["path"]))
    return classified

def import_file(base_url: str, entity: str, path: str, dry_run: bool = False) -> bool:
    url = f"{base_url.rstrip('/')}/import/csv"
    params = {"entity": entity}
    if dry_run:
        print(f"[dry-run] POST {url}?entity={entity}  file={path}")
        return True
    with open(path, "rb") as f:
        files = {"file": (os.path.basename(path), f, "text/csv")}
        resp = requests.post(url, params=params, files=files, timeout=120)
    if resp.status_code == 200:
        print(f"[ok] {entity:<22} ← {path}")
        return True
    print(f"[ERR] {entity:<22} ← {path}\n      {resp.status_code} {resp.text[:400]}")
    return False

def run_import(data_dir: str = DATA_DIR,
               pack: str | None = None,
               base_url: str = DEFAULT_BASE_URL,
               manifest_path: str = MANIFEST_PATH,
               dry_run: bool = False) -> dict:
    """Callable entrypoint: returns a dict with plan and results."""
    manifest = load_manifest(manifest_path)
    if manifest and "base_url" in manifest and base_url == DEFAULT_BASE_URL:
        base_url = manifest["base_url"]

    csvs = discover_csvs(data_dir, pack=pack)
    if not csvs:
        return {
            "ok": False,
            "base_url": base_url,
            "plan": [],
            "results": [],
            "message": f"No CSVs found under {data_dir}" + (f"/packs/{pack}" if pack else "")
        }
    plan = classify_files(csvs, manifest)
    if not plan:
        return {
            "ok": False,
            "base_url": base_url,
            "plan": [],
            "results": [],
            "message": f"Found {len(csvs)} CSVs but none matched known entities. Check file names or manifest."
        }
    results = []
    ok_all = True
    for item in plan:
        ok = import_file(base_url, item["entity"], item["path"], dry_run=dry_run)
        results.append({"entity": item["entity"], "path": item["path"], "ok": ok})
        if not ok:
            ok_all = False
    return {"ok": ok_all, "base_url": base_url, "plan": plan, "results": results}

def main():
    ap = argparse.ArgumentParser(description="Import CSVs in dependency order.")
    ap.add_argument("--data", default=DATA_DIR, help="Root data folder (default: ./data)")
    ap.add_argument("--pack", default=None, help="Only import a specific pack under data/packs/<pack>")
    ap.add_argument("--base-url", default=None, help="Importer base URL (default env IMPORT_BASE_URL or http://localhost:8000)")
    ap.add_argument("--manifest", default=MANIFEST_PATH, help="Optional import_manifest.json path")
    ap.add_argument("--dry-run", action="store_true", help="Don’t POST, just show the plan")
    args = ap.parse_args()

    base_url = args.base_url or DEFAULT_BASE_URL
    summary = run_import(data_dir=args.data, pack=args.pack, base_url=base_url,
                         manifest_path=args.manifest, dry_run=args.dry_run)

    print(f"Importer: {summary['base_url']}")
    print(f"Data root: {args.data}  Pack: {args.pack or '(all)'}")
    print("— Import plan —")
    for item in summary["plan"]:
        print(f"{item['order']:>3}  {item['entity']:<22}  {item['path']}")
    sys.exit(0 if summary["ok"] else 2)

if __name__ == "__main__":
    main()
