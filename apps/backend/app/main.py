from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.settings import settings
from app.routers import books as books_router
import os

app = FastAPI(title=settings.APP_NAME)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# --- API-Key very light (solo per rotte /v1/*) ---
@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    if request.url.path.startswith("/v1/"):
        expected = settings.OWNER_API_KEY.strip()
        if expected:
            provided = request.headers.get("X-API-Key", "").strip()
            if provided != expected:
                raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")
    return await call_next(request)

@app.get("/")
def root():
    return {"message": "EccomiBook – core API attive ✨", "docs": "/docs"}

@app.get("/health")
def health():
    return {
        "status": "ok",
        "env": settings.APP_ENV,
        "storage_dir": settings.DATA_DIR,
    }

# Routers (tutto il programma vive sotto /v1)
app.include_router(books_router.router, prefix="/v1", tags=["books"])
