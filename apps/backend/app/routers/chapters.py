# apps/backend/app/routers/chapters.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime
from .. import storage

router = APIRouter(tags=["chapters"])

# ─────────────────────────────────────────────────────────
# Schemi input
# ─────────────────────────────────────────────────────────
class ChapterSaveIn(BaseModel):
    book_id: str
    chapter_id: str
    content: str

class ChapterPutIn(BaseModel):
    content: str

# ─────────────────────────────────────────────────────────
# Helper interni
# ─────────────────────────────────────────────────────────
def _ensure_book_exists(app, book_id: str):
    books: dict = getattr(app.state, "books", {})
    book = books.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    return books, book

def _read_chapter(book_id: str, chapter_id: str) -> dict:
    exists, content, rel = storage.read_chapter_file(book_id, chapter_id)
    # Non alziamo 404 se il file non esiste: restituiamo exists=False e content=""
    return {"exists": exists, "book_id": book_id, "chapter_id": chapter_id, "content": content, "path": rel}

def _save_chapter_and_index(app, book_id: str, chapter_id: str, content: str) -> dict:
    books, book = _ensure_book_exists(app, book_id)

    # Scrivi file su disco e ottieni path relativo
    rel_path = storage.save_chapter_file(book_id, chapter_id, content or "")

    # Aggiorna indice capitoli dentro il "DB" in memoria
    chapters = book.setdefault("chapters", [])
    now_iso = datetime.utcnow().isoformat() + "Z"

    for ch in chapters:
        if ch.get("id") == chapter_id:
            ch["path"] = rel_path
            ch["updated_at"] = now_iso
            break
    else:
        chapters.append({
            "id": chapter_id,
            "title": chapter_id,
            "path": rel_path,
            "updated_at": now_iso,
        })

    # Persisti il DB su disco
    storage.save_books_to_disk(books)

    return {"ok": True, "book_id": book_id, "chapter_id": chapter_id, "path": rel_path, "bytes": len((content or "").encode("utf-8"))}

# ─────────────────────────────────────────────────────────
# Rotte COMPAT storiche (le tue attuali)
#   - POST  /chapters/save        {book_id, chapter_id, content}
#   - GET   /chapters/{book}/{chapter}
# ─────────────────────────────────────────────────────────
@router.post("/chapters/save")
def chapters_save(req: Request, payload: ChapterSaveIn):
    return _save_chapter_and_index(req.app, payload.book_id, payload.chapter_id, payload.content)

@router.get("/chapters/{book_id}/{chapter_id}")
def chapters_read(book_id: str, chapter_id: str):
    # Non solleva FileNotFoundError: ritorna exists/content vuoti se non c'è
    return _read_chapter(book_id, chapter_id)

# ─────────────────────────────────────────────────────────
# Rotte “REST” usate dal frontend nuovo
#   - GET   /books/{book}/chapters/{chapter}
#   - PUT   /books/{book}/chapters/{chapter}   {content}
# ─────────────────────────────────────────────────────────
@router.get("/books/{book_id}/chapters/{chapter_id}")
def get_chapter(book_id: str, chapter_id: str):
    return _read_chapter(book_id, chapter_id)

@router.put("/books/{book_id}/chapters/{chapter_id}")
def put_chapter(req: Request, book_id: str, chapter_id: str, payload: ChapterPutIn):
    return _save_chapter_and_index(req.app, book_id, chapter_id, payload.content)
