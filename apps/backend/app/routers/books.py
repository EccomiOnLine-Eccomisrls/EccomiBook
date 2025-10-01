# apps/backend/app/routers/books.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
import re

from app import storage

router = APIRouter()

# --------- Schemi ---------
class BookIn(BaseModel):
    title: str
    author: Optional[str] = None
    abstract: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    language: str = "it"
    plan: Optional[str] = None
    chapters: List[Dict[str, Any]] = []

class BookUpdateIn(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    abstract: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    language: Optional[str] = None
    plan: Optional[str] = None

class ReorderIn(BaseModel):
    order: List[str]  # lista di chapter.id nel nuovo ordine

class ChapterCreateIn(BaseModel):
    title: Optional[str] = "Nuovo capitolo"
    content: Optional[str] = ""
    language: Optional[str] = None

class ChapterUpdateIn(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    language: Optional[str] = None

# --------- Helpers ---------
def _ensure_chapters(book: Dict[str, Any]) -> None:
    if not book.get("chapters"):
        book["chapters"] = []

def _ensure_first_chapter(book: Dict[str, Any]) -> None:
    _ensure_chapters(book)
    if not book["chapters"]:
        book["chapters"].append({
            "id": "ch_0001",
            "title": "Capitolo 1",
            "content": "",
            "language": book.get("language", "it")
        })

def _next_chapter_id(book: Dict[str, Any]) -> str:
    _ensure_chapters(book)
    max_n = 0
    for ch in book["chapters"]:
        m = re.match(r"^ch_(\d{4})$", str(ch.get("id", "")))
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"ch_{(max_n + 1):04d}"

def _find_chapter_index(book: Dict[str, Any], chapter_id: str) -> int:
    _ensure_chapters(book)
    for i, ch in enumerate(book["chapters"]):
        if ch.get("id") == chapter_id:
            return i
    raise HTTPException(status_code=404, detail="Capitolo non trovato")

# --------- Endpoints libri ---------
@router.get("/books")
def list_books():
    return storage.load_books()

@router.get("/books/{book_id}")
def get_book(book_id: str):
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    return b

@router.post("/books", status_code=201)
def create_book(payload: BookIn):
    now = datetime.utcnow().isoformat()
    new_id = f"book_{int(datetime.utcnow().timestamp())}"
    book = payload.dict()
    book.update({"id": new_id, "created_at": now, "updated_at": now})
    _ensure_chapters(book)  # solo array vuoto, nessun capitolo
    storage.persist_book(book)
    return book

@router.patch("/books/{book_id}")
def update_book(book_id: str, payload: BookUpdateIn):
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    data = payload.dict(exclude_unset=True)
    for k, v in data.items():
        b[k] = v
    b["updated_at"] = datetime.utcnow().isoformat()
    storage.persist_book(b)
    return b

# --------- Endpoints capitoli ---------
@router.post("/books/{book_id}/chapters", status_code=201)
def create_chapter(book_id: str, payload: ChapterCreateIn = Body(default=ChapterCreateIn())):
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    _ensure_chapters(b)
    new_id = _next_chapter_id(b)
    chapter = {
        "id": new_id,
        "title": payload.title or "Nuovo capitolo",
        "content": payload.content or "",
        "language": payload.language or b.get("language", "it")
    }
    b["chapters"].append(chapter)
    b["updated_at"] = datetime.utcnow().isoformat()
    storage.persist_book(b)
    return {"ok": True, "chapter": chapter, "count": len(b["chapters"])}

@router.get("/books/{book_id}/chapters/{chapter_id}")
def get_chapter(book_id: str, chapter_id: str):
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    ci = _find_chapter_index(b, chapter_id)
    return b["chapters"][ci]

# --- aggiungi questo endpoint vicino agli altri dei capitoli ---

@router.get("/books/{book_id}/chapters", summary="List Chapters")
def list_chapters(book_id: str):
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    return {"items": b.get("chapters", [])}

@router.put("/books/{book_id}/chapters/{chapter_id}")
def update_chapter(book_id: str, chapter_id: str, payload: ChapterUpdateIn = Body(...)):
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    _ensure_chapters(b)
    ci = _find_chapter_index(b, chapter_id)
    ch = b["chapters"][ci]

    data = payload.dict(exclude_unset=True)
    if data.get("title") is not None:
        ch["title"] = data["title"]
    if data.get("content") is not None:
        ch["content"] = data["content"]
    if data.get("language") is not None:
        ch["language"] = data["language"]

    b["chapters"][ci] = ch
    b["updated_at"] = datetime.utcnow().isoformat()
    storage.persist_book(b)
    return {"ok": True, "chapter": ch}

@router.delete("/books/{book_id}/chapters/{chapter_id}")
def delete_chapter(book_id: str, chapter_id: str):
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    _ensure_chapters(b)
    ci = _find_chapter_index(b, chapter_id)
    removed = b["chapters"].pop(ci)

    # ❌ rimosso: non ricreiamo più un capitolo se array vuoto

    b["updated_at"] = datetime.utcnow().isoformat()
    storage.persist_book(b)
    return {"ok": True, "removed": removed["id"], "count": len(b["chapters"])}

@router.post("/books/{book_id}/chapters/reorder")
def reorder_chapters(book_id: str, payload: ReorderIn = Body(...)):
    try:
        updated = storage.reorder_chapters(book_id, payload.order)
        return {"ok": True, "book": updated, "count": len(updated.get("chapters", []))}
    except ValueError:
        raise HTTPException(status_code=404, detail="Libro non trovato")
