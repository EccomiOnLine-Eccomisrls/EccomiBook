from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import shutil

from .settings import get_settings
from . import storage
from .routers import books as books_router
from .routers import generate as generate_router
from .routers import auth as auth_router
from .routers import admin as admin_router   # pannello OWNER_FULL

from .users import load_users, seed_demo_users  # gestione utenti/piani

app = FastAPI(
    title="EccomiBook Backend",
    version="0.1.0",
    openapi_url="/openapi.json",
    docs_url="/",
)

# Mount statici sul DISCO PERSISTENTE
storage.ensure_dirs()
app.mount(
    "/static/chapters",
    StaticFiles(directory=str(storage.BASE_DIR / "chapters")),
    name="chapters",
)
app.mount(
    "/static/books",
    StaticFiles(directory=str(storage.BASE_DIR / "books")),
    name="books",
)

# CORS (aperto: adatta se vuoi restringere)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup() -> None:
    # directory persistenti
    storage.ensure_dirs()

    # piccolo DB in memoria
    app.state.books = {}          # {book_id: {...}}
    app.state.counters = {"books": 0}

    # utenti/piani: carica da disco + seed demo (solo MVP)
load_users()
if not getattr(app.state, "seeded", False):
    seed_demo_users()  # solo in dev/MVP
    app.state.seeded = True

    settings = get_settings()
    print(f"✅ APP STARTED | ENV: {settings.environment} | STORAGE_ROOT={storage.BASE_DIR}")
@app.get("/health", tags=["default"])
def health():
    return {"ok": True}

@app.get("/test", tags=["default"])
def test_page():
    return {"ok": True, "msg": "test"}

# Download file esportati (supporta sottocartelle)
@app.get("/downloads/{subpath:path}", tags=["default"], summary="Download File")
def download_file(subpath: str):
    full_path = (storage.BASE_DIR / subpath).resolve()
    if not str(full_path).startswith(str(storage.BASE_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Percorso non valido")
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File non trovato")
    return FileResponse(full_path)

# Diagnostica storage (utile per verificare Render Disk)
@app.get("/debug/storage", tags=["default"])
def debug_storage():
    root = storage.BASE_DIR
    total, used, free = shutil.disk_usage(root)
    chapters = sorted([p.name for p in (root / "chapters").glob("*.pdf")])[:50]
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

# Routers
app.include_router(auth_router.router, tags=["default"])
app.include_router(books_router.router, tags=["default"])
app.include_router(generate_router.router, tags=["default"])
app.include_router(admin_router.router, tags=["admin"])  # pannello OWNER_FULL
