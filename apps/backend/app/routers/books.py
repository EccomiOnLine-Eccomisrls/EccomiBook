# apps/backend/app/routers/books.py
from fastapi import APIRouter, HTTPException, Body, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
import uuid, re
from typing import Any
from datetime import datetime
from pathlib import Path

from .. import storage

router = APIRouter()

# ─────────────────────────────────────────────────────────
# Modelli
# ─────────────────────────────────────────────────────────
class BookIn(BaseModel):
    title: str
    author: str | None = None
    abstract: str | None = None
    description: str | None = None
    genre: str | None = None
    language: str = "it"
    plan: str | None = None
    chapters: list[dict] = []  # [{id, path?, title?, updated_at?}]

class ChapterUpdate(BaseModel):
    content: str

# ─────────────────────────────────────────────────────────
# Util
# ─────────────────────────────────────────────────────────
def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")

def _books_db(request: Request) -> dict[str, dict[str, Any]]:
    # "DB" in-memory popolato in app.main.on_startup()
    return request.app.state.books

# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────
@router.get("/books", tags=["books"])
def list_books(request: Request):
    return list(_books_db(request).values())

@router.get("/books/{book_id}", tags=["books"])
def get_book(book_id: str, request: Request):
    book = _books_db(request).get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    return book

@router.post("/books/create", tags=["books"])
def create_book(request: Request, payload: BookIn = Body(...)):
    slug = slugify(payload.title) or "senza-titolo"
    random_part = uuid.uuid4().hex[:6]
    book_id = f"book_{slug}_{random_part}"

    books_db = _books_db(request)
    books_db[book_id] = {
        "id": book_id,
        "title": payload.title,
        "author": payload.author,
        "abstract": payload.abstract,
        "description": payload.description,
        "genre": payload.genre,
        "language": payload.language,
        "plan": payload.plan or "START",
        "chapters": payload.chapters or [],
    }
    storage.save_books_to_disk(books_db)
    return {"book_id": book_id, "title": payload.title, "chapters_count": len(payload.chapters or [])}

@router.delete("/books/{book_id}", tags=["books"], status_code=204)
def delete_book(request: Request, book_id: str):
    books_db = _books_db(request)
    if book_id not in books_db:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    books_db.pop(book_id, None)
    storage.save_books_to_disk(books_db)
    return

# ── LETTURA CAPITOLO (per pulsante "Apri")
@router.get("/books/{book_id}/chapters/{chapter_id}", tags=["books"])
def get_chapter(book_id: str, chapter_id: str, request: Request):
    if book_id not in _books_db(request):
        raise HTTPException(status_code=404, detail="Libro non trovato")
    exists, content, rel_path = storage.read_chapter_file(book_id, chapter_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Capitolo non trovato")
    return {"book_id": book_id, "chapter_id": chapter_id, "path": rel_path, "content": content, "exists": True}

# ── CREAZIONE/AGGIORNAMENTO CAPITOLO
@router.put("/books/{book_id}/chapters/{chapter_id}", tags=["books"])
def upsert_chapter(request: Request, book_id: str, chapter_id: str, payload: ChapterUpdate = Body(...)):
    books_db = _books_db(request)
    book = books_db.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    rel_path = storage.save_chapter_file(book_id, chapter_id, payload.content or "")
    chapters = book.setdefault("chapters", [])
    now = datetime.utcnow().isoformat() + "Z"
    idx = next((i for i, ch in enumerate(chapters) if (ch.get("id") == chapter_id)), -1)

    if idx >= 0:
        chapters[idx]["path"] = rel_path
        chapters[idx]["updated_at"] = now
    else:
        chapters.append({"id": chapter_id, "title": chapter_id, "path": rel_path, "updated_at": now})

    storage.save_books_to_disk(books_db)
    return {"ok": True, "book_id": book_id, "chapter": {"id": chapter_id, "path": rel_path, "updated_at": now}}

# ── ELIMINA CAPITOLO
@router.delete("/books/{book_id}/chapters/{chapter_id}", tags=["books"], status_code=204)
def delete_chapter(book_id: str, chapter_id: str, request: Request):
    books_db = _books_db(request)
    book = books_db.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    # rimuovi dall'elenco
    chapters = book.get("chapters", [])
    book["chapters"] = [ch for ch in chapters if ch.get("id") != chapter_id]

    # rimuovi file .md se esiste
    md_path: Path = storage.chapter_path(book_id, chapter_id)
    if md_path.exists():
        md_path.unlink(missing_ok=True)

    storage.save_books_to_disk(books_db)
    return

# ── EXPORT CAPITOLO (MD/TXT/PDF)
@router.get("/books/{book_id}/chapters/{chapter_id}.md", tags=["books"])
def export_chapter_md(book_id: str, chapter_id: str):
    exists, content, _ = storage.read_chapter_file(book_id, chapter_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Capitolo non trovato")
    return PlainTextResponse(content, media_type="text/markdown")

@router.get("/books/{book_id}/chapters/{chapter_id}.txt", tags=["books"])
def export_chapter_txt(book_id: str, chapter_id: str):
    exists, content, _ = storage.read_chapter_file(book_id, chapter_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Capitolo non trovato")
    return PlainTextResponse(content, media_type="text/plain")

@router.get("/books/{book_id}/chapters/{chapter_id}.pdf", tags=["books"])
def export_chapter_pdf(book_id: str, chapter_id: str):
    exists, content, _ = storage.read_chapter_file(book_id, chapter_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Capitolo non trovato")
    pdf_path = storage.make_chapter_pdf(book_id, chapter_id, content or "")
    return FileResponse(pdf_path, filename=f"{chapter_id}.pdf", media_type="application/pdf")
