from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from .settings import get_settings
from . import storage
from .routers import books as books_router
from .routers import generate as generate_router
from .routers import auth as auth_router

app = FastAPI(
    title="EccomiBook Backend",
    version="0.1.0",
    openapi_url="/openapi.json",
    docs_url="/",
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
    # directory persistente/sicura per i file export
    storage.ensure_dirs()
    # piccolo DB in memoria
    app.state.books = {}  # {book_id: {...}}
    # plan counters ecc. se serviranno
    app.state.counters = {"books": 0}
    settings = get_settings()
    print(f"✅ APP STARTED | ENV: {settings.environment}")


@app.get("/health", tags=["default"])
def health():
    return {"ok": True}


@app.get("/test", tags=["default"])
def test_page():
    return {"ok": True, "msg": "test"}


# Download file esportati
@app.get("/downloads/{filename}", tags=["default"], summary="Download File")
def download_file(filename: str):
    file_path = storage.file_path(filename)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File non trovato")
    return FileResponse(file_path)


# Routers
app.include_router(auth_router.router, tags=["default"])      # solo per header spec
app.include_router(books_router.router, tags=["default"])     # /books, /books/{id}/chapters
app.include_router(generate_router.router, tags=["default"])  # /generate/chapter, /generate/export/book/{id}
