from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path

from ..core.templates import templates
from ..import_runner import run_import, DATA_DIR, MANIFEST_PATH, DEFAULT_BASE_URL

router = APIRouter(prefix="/admin/import", tags=["admin"])

@router.get("", response_class=HTMLResponse)
def import_page(request: Request):
    # Render the page with a button; values shown for sanity/debug
    return templates.TemplateResponse(
        "admin_import.html",
        {
            "request": request,
            "data_dir": DATA_DIR,
            "manifest_path": MANIFEST_PATH,
            "base_url": DEFAULT_BASE_URL,
        },
    )

@router.post("/run", response_class=JSONResponse)
def run_import_now(
    request: Request,
    data_dir: str = DATA_DIR,
    manifest_path: str = MANIFEST_PATH,
    base_url: str = DEFAULT_BASE_URL,
    pack: str | None = None,
    dry_run: bool = False,
):
    summary = run_import(
        data_dir=data_dir,
        pack=pack,
        base_url=base_url,
        manifest_path=manifest_path,
        dry_run=dry_run,
    )
    # Compact payload for the page
    compact = {
        "ok": summary["ok"],
        "base_url": summary["base_url"],
        "message": summary.get("message"),
        "found": len(summary.get("plan", [])),
        "results": [
            {"entity": r["entity"], "ok": r["ok"], "path": str(Path(r["path"]).name)}
            for r in summary.get("results", [])
        ],
    }
    return compact
