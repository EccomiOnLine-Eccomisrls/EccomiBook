# apps/backend/app/main.py
from __future__ import annotations

from pathlib import Path
import shutil

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .settings import get_settings
from . import storage
from .routers import books as books_router
from .routers import generate as generate_router
from .routers import books_export as books_export_router  # export intero libro

app = FastAPI(
    title="EccomiBook Backend",
    version="0.2.0",
    openapi_url="/openapi.json",
    docs_url="/docs",     # Swagger UI su /docs
    redoc_url="/redoc",   # ReDoc opzionale
)

# Root "gentile" → reindirizza alle docs
@app.get("/", include_in_schema=False)
def home():
    return HTMLResponse(
        "<!doctype html><meta http-equiv='refresh' content='0; url=/docs'>"
        "<p>Vai alle <a href='/docs'>API Docs</a>.</p>"
    )

# Favicon: serve /static/favicon.ico se esiste, altrimenti 204 (niente 404 in log)
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    fav = Path("static/favicon.ico")
    if fav.exists():
        return FileResponse(fav)
    return Response(status_code=204)

# Inizializza filesystem e mount statici
storage.ensure_dirs()
app.mount("/static/chapters", StaticFiles(directory=str(storage.CHAPTERS_DIR)), name="chapters")
app.mount("/static/books", StaticFiles(directory=str(storage.BOOKS_DIR)), name="books")

# CORS dev-friendly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup() -> None:
    storage.ensure_dirs()
    # Carica da DISCO e sincronizza cache + app.state
    books = storage.load_books_from_disk()
    storage.BOOKS_CACHE = books
    app.state.books = books
    app.state.counters = {"books": len(books)}

    settings = get_settings()
    print(f"✅ APP STARTED | ENV: {settings.environment} | STORAGE_ROOT={storage.BASE_DIR}")

@app.on_event("shutdown")
def on_shutdown() -> None:
    # Salva su disco lo stato più aggiornato
    books = getattr(app.state, "books", None) or storage.BOOKS_CACHE or []
    storage.save_books_to_disk(books)
    print("💾 Books salvati su disco in shutdown.")

@app.get("/health", tags=["default"])
def health():
    return {"ok": True}

@app.get("/test", tags=["default"])
def test_page():
    return {"ok": True, "msg": "test"}

# Download generico (se serve)
@app.get("/downloads/{subpath:path}", tags=["default"], summary="Download File")
def download_file(subpath: str):
    full_path = (storage.BASE_DIR / subpath).resolve()
    if not str(full_path).startswith(str(storage.BASE_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Percorso non valido")
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File non trovato")
    return FileResponse(full_path)

# Diagnostica storage
@app.get("/debug/storage", tags=["default"])
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
# ---------------- ROUTES EXTRA ----------------
@app.get("/")
def root():
    """Healthcheck e messaggio di benvenuto"""
    return JSONResponse({"status": "ok", "service": "EccomiBook Backend", "version": "0.2.0"})
# Routers
app.include_router(books_router.router, tags=["books"])
app.include_router(generate_router.router, tags=["generate"])
app.include_router(books_export_router.router, tags=["export"])
