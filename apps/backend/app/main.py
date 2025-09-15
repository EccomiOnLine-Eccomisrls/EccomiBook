from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os, time

from apps.backend.app import storage

app = FastAPI(title="EccomiBook Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restringi in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Startup ----------
@app.on_event("startup")
def on_startup():
    storage.ensure_dirs()
    print(f"✅ APP STARTED | ENV: {os.getenv('APP_ENV','production')} | STORAGE_DIR={storage.DEFAULT_DIR}")

# ---------- Health & Root ----------
@app.get("/")
def root():
    return {"message": "EccomiBook Backend"}

@app.get("/health")
def health():
    try:
        storage.ensure_dirs()
        ok = True
    except Exception as e:
        ok = False
    return {"status": "ok" if ok else "degraded", "env": os.getenv("APP_ENV","production"), "service": "EccomiBook Backend"}

# ---------- Schemi ----------
class BookCreate(BaseModel):
    title: str
    topic: Optional[str] = ""
    genre: Optional[str] = ""
    language: Optional[str] = "it"

class ChapterCreate(BaseModel):
    title: str
    prompt: Optional[str] = ""
    outline: Optional[str] = ""
    text: Optional[str] = ""   # opzionale: se vuoto, ne mettiamo uno placeholder

# ---------- Books ----------
@app.get("/books")
def list_books():
    return storage.list_books()

@app.post("/books")
def create_book(body: BookCreate):
    book = storage.create_book(
        title=body.title,
        topic=body.topic or "",
        genre=body.genre or "",
        language=body.language or "it",
    )
    return {"ok": True, "book": book}

@app.get("/books/{book_id}")
def get_book(book_id: str):
    book = storage.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

# ---------- Chapters ----------
@app.get("/books/{book_id}/chapters")
def list_book_chapters(book_id: str):
    try:
        chapters = storage.list_chapters(book_id)
        return {"book_id": book_id, "chapters": chapters}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Book not found")

@app.post("/books/{book_id}/chapters")
def add_chapter(book_id: str, body: ChapterCreate):
    try:
        ch = storage.add_chapter(
            book_id=book_id,
            title=body.title,
            prompt=body.prompt or "",
            outline=body.outline or "",
            text=body.text or "",
        )
        return {"ok": True, "book_id": book_id, "chapter": ch}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Book not found")

@app.get("/books/{book_id}/chapters/{chapter_id}")
def get_chapter(book_id: str, chapter_id: str):
    ch = storage.get_chapter(book_id, chapter_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return ch

# ---------- Export ----------
@app.post("/generate/export/book/{book_id}")
def generate_export(book_id: str, format: str = Query("pdf", pattern="^(pdf)$")):
    book = storage.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if format != "pdf":
        raise HTTPException(status_code=400, detail="Only pdf is supported right now")

    path = storage.generate_pdf_for_book(book)
    filename = os.path.basename(path)
    url = f"/downloads/{filename}"
    return {
        "ok": True,
        "book_id": book_id,
        "format": format,
        "file_name": filename,
        "url": url,
        "chapters": len(book.get("chapters", [])),
        "generated_at": int(time.time()),
    }

@app.get("/downloads/{filename}")
def downloads(filename: str):
    p = storage.exported_file_path(filename)
    if not p:
        raise HTTPException(status_code=404, detail="File non trovato")
    return FileResponse(p, media_type="application/pdf", filename=filename)
