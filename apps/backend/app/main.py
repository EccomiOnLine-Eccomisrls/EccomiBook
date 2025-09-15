from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import books, generate

app = FastAPI(title="EccomiBook Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(books.router)
app.include_router(generate.router)

@app.get("/")
def root():
    return {"message": "EccomiBook Backend"}

@app.get("/health")
def health():
    return {"status": "ok", "env": "production", "service": "EccomiBook Backend"}
