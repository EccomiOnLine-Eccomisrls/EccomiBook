# apps/backend/app/main.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import storage
from .routers import books as books_router
from .routers import books_export as books_export_router
from .routers import generate as generate_router  

app = FastAPI(
    title="EccomiBook Backend",
    version="0.3.2",
    openapi_url="/openapi.json",
    docs_url="/",
)

# FS
storage.ensure_dirs()
app.mount("/static/chapters", StaticFiles(directory=str(storage.CHAPTERS_DIR)), name="chapters")
app.mount("/static/books", StaticFiles(directory=str(storage.BOOKS_DIR)), name="books")

# CORS (aperto: ok per status page su dominio diverso)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # se preferisci, metti l’URL del tuo frontend
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,   # importante: se tieni "*", non mettere True qui
)

# Routers
app.include_router(books_router.router,       prefix="/api/v1", tags=["books"])
app.include_router(books_export_router.router, prefix="/api/v1", tags=["export"])
app.include_router(generate_router.router,   prefix="/api/v1", tags=["ai"])

# Health endpoints (sia root che /api/v1 per compatibilità con la status page)
@app.get("/health")
def health_root():
    return {"ok": True, "version": "0.3.2"}

@app.get("/api/v1/health")
def health_api():
    return {"ok": True, "version": "0.3.2"}


