# apps/backend/app/main.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import storage
from .routers import books as books_router
from .routers import books_export as books_export_router
# se usi anche l'AI, tieni questo import:
# from .routers import generate as generate_router

app = FastAPI(
    title="EccomiBook Backend",
    version="0.3.1",
    openapi_url="/openapi.json",
    docs_url="/",
)

# FS
storage.ensure_dirs()
app.mount("/static/chapters", StaticFiles(directory=str(storage.CHAPTERS_DIR)), name="chapters")
app.mount("/static/books", StaticFiles(directory=str(storage.BOOKS_DIR)), name="books")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(books_router.router, prefix="/api/v1", tags=["books"])
app.include_router(books_export_router.router, prefix="/api/v1", tags=["export"])
# app.include_router(generate_router.router, prefix="/api/v1", tags=["ai"])

@app.get("/health")
def health():
    return {"ok": True, "version": "0.3.1"}

