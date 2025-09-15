# app/main.py
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.settings import settings
from app.models import Plan
from app.routers import books, generate


app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Auth owner per endpoint admin futuri ---
def require_owner(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    if not settings.OWNER_API_KEY:
        raise HTTPException(status_code=500, detail="OWNER_API_KEY non configurato")
    if x_api_key != settings.OWNER_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized (owner)")
    return True


@app.get("/")
def root():
    return {"message": "EccomiBook Backend"}


@app.get("/health")
def health():
    return {"status": "ok", "env": settings.APP_ENV, "service": settings.APP_NAME}


# Routers core
app.include_router(books.router)
app.include_router(generate.router)
