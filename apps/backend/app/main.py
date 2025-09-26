# apps/backend/app/main.py
from __future__ import annotations

from pathlib import Path
import logging
import shutil
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .settings import get_settings
from . import storage
from .routers import books as books_router
from .routers import generate as generate_router
from .routers import books_export as books_export_router  # export intero libro

# =========================
# Config dinamica da settings
# =========================
settings = get_settings()
ENV = (settings.environment or "development").lower()

# ✅ Docs & ReDoc SEMPRE attive (anche in production)
DOCS_URL  = "/docs"
REDOC_URL = "/redoc"

# CORS presi da settings
CORS_ALLOW_ORIGINS = getattr(settings, "cors_allow_origins", None) or ["*"]

# Prefisso versionamento API
API_PREFIX = "/api/v1"

# =========================
# FastAPI app
# =========================
app = FastAPI(
    title="EccomiBook Backend",
    version="0.2.0",
    openapi_url="/openapi.json",
    docs_url=DOCS_URL,
    redoc_url=REDOC_URL,
)

# =========================
# Homepage HTML “gentile”
# =========================
@app.get("/", include_in_schema=False)
def home_get():
    docs_btn  = f"<p><a class='button' href='{DOCS_URL}'>Vai alle API Docs</a></p>" if DOCS_URL else ""
    redoc_btn = f"<p><a class='button' href='{REDOC_URL}'>Vai alla ReDoc</a></p>"   if REDOC_URL else ""
    return HTMLResponse(f"""
    <!doctype html>
    <html lang="it">
    <head>
      <meta charset="utf-8">
      <title>EccomiBook Backend</title>
      <meta name="viewport" content="width=device-width, initial-scale=1"/>
      <style>
        :root {{ --c1:#d62828; --c2:#0077b6; --c2h:#0096c7; }}
        body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
                text-align: center; margin: 6vh 4vw; background:#fafafa; color:#222; }}
        h1 {{ color: var(--c1); font-size: clamp(28px,4vw,42px); margin: .2em 0 .4em; }}
        p  {{ margin: 1em 0; line-height: 1.4; }}
        .muted {{ color:#666; font-size: 0.95em; }}
        a.button {{
          display:inline-block; padding:10px 20px; background:var(--c2); color:#fff;
          text-decoration:none; border-radius:8px; font-weight:600; margin:.35rem;
        }}
        a.button:hover {{ background:var(--c2h); }}
        .grid {{ display:flex; gap:12px; justify-content:center; flex-wrap:wrap; }}
        code {{ background:#f1f1f1; padding:.2em .4em; border-radius:4px; }}
      </style>
    </head>
    <body>
      <h1>✅ EccomiBook Backend attivo</h1>
      <p>Benvenuto! Questo è il backend del progetto <strong>EccomiBook</strong>.</p>
      <div class="grid">
        {docs_btn}
        {redoc_btn}
        <p><a class="button" href="/health">Health</a></p>
        <p><a class="button" href="{API_PREFIX}/health">API Health</a></p>
      </div>
      <p class="muted">Ambiente: <code>{ENV}</code> · Versione: <code>0.2.0</code></p>
    </body>
    </html>
    """)

# ✅ Gestione esplicita di HEAD / per evitare 405 nei log
@app.head("/", include_in_schema=False)
def home_head():
    return Response(status_code=200)

# =========================
# Favicon “silenziosa”
# =========================
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    fav = Path("static/favicon.ico")
    if fav.exists():
        return FileResponse(fav)
    return Response(status_code=204)

# =========================
# Middleware: logging richieste (usa logger tuo!)
# =========================
logger = logging.getLogger("eccomibook")  # ⬅️ NON usare "uvicorn.access"

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"➡️  {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"⬅️  {request.method} {request.url} {response.status_code}")
    return response

# =========================
# Startup / Shutdown
# =========================
@app.on_event("startup")
def on_startup() -> None:
    storage.ensure_dirs()
    books = storage.load_books_from_disk()
    storage.BOOKS_CACHE = books
    app.state.books = books
    app.state.counters = {"books": len(books)}
    print(f"✅ APP STARTED | ENV: {ENV} | STORAGE_ROOT={storage.BASE_DIR}")

@app.on_event("shutdown")
def on_shutdown() -> None:
    books = getattr(app.state, "books", None) or storage.BOOKS_CACHE or []
    storage.save_books_to_disk(books)
    print("💾 Books salvati su disco in shutdown.")

# =========================
# Health & Test
# =========================
@app.get("/health", tags=["default"])
def health_root():
    return {"ok": True, "env": ENV, "service": "eccomibook", "version": "0.2.0"}

@app.get(f"{API_PREFIX}/health", tags=["default"])
def health_api():
    return {"ok": True, "env": ENV, "service": "eccomibook", "version": "0.2.0"}

# =========================
# Download generico sicuro
# =========================
@app.get(f"{API_PREFIX}/downloads/{{subpath:path}}", tags=["default"], summary="Download File")
def download_file(subpath: str):
    full_path = (storage.BASE_DIR / subpath).resolve()
    if not str(full_path).startswith(str(storage.BASE_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Percorso non valido")
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File non trovato")
    return FileResponse(full_path)

# =========================
# Debug storage
# =========================
@app.get(f"{API_PREFIX}/debug/storage", tags=["default"])
def debug_storage():
    root = storage.BASE_DIR
    total, used, free = shutil.disk_usage(root)
    chapters = sorted([p.as_posix() for p in (root / "chapters").rglob("*.md")])[:50]
    books = sorted([p.name for p in (root / "books").glob("*.pdf")])[:50]
    return {
        "storage_root": str(root),
        "exists": root.exists(),
        "chapters_count": len(chapters),
        "books_count": len(books),
        "chapters_sample": chapters,
        "books_sample": books,
        "disk_bytes": {"total": total, "used": used, "free": free},
    }

# =========================
# Static mounts
# =========================
storage.ensure_dirs()
app.mount("/static/chapters", StaticFiles(directory=str(storage.CHAPTERS_DIR)), name="chapters")
app.mount("/static/books", StaticFiles(directory=str(storage.BOOKS_DIR)), name="books")

# =========================
# CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    # allow_credentials=False  # per ora non servono cookie/sessioni
)

# =========================
# Routers (versionati)
# =========================
app.include_router(books_router.router,  prefix=f"{API_PREFIX}/books",    tags=["books"])
app.include_router(generate_router.router, prefix=f"{API_PREFIX}",        tags=["generate"])
app.include_router(books_export_router.router, prefix=f"{API_PREFIX}/export", tags=["export"])

# =========================
# Ping JSON (facoltativo)
# =========================
@app.get(f"{API_PREFIX}/ping", include_in_schema=False)
def ping():
    return JSONResponse({"pong": True, "env": ENV})
