from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from uuid import uuid4
from .. import storage

router = APIRouter(prefix="/books", tags=["books"])

# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class ChapterRef(BaseModel):
    id: str
    title: str | None = None
    path: str | None = None

class BookCreateIn(BaseModel):
    title: str = Field(..., min_length=1)
    author: str = "EccomiBook"
    language: str = "it"
    chapters: List[ChapterRef] = Field(default_factory=list)

# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────
def _get_db(req: Request) -> Dict[str, Dict[str, Any]]:
    # assicura che l'app abbia il DB in memoria
    if not hasattr(req.app.state, "books") or not isinstance(req.app.state.books, dict):
        req.app.state.books = storage.load_books_from_disk()
    return req.app.state.books  # dict: {book_id: book_dict}

# ─────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────
@router.get("")
def list_books(req: Request):
    db = _get_db(req)
    # ritorna lista di libri
    return list(db.values())

@router.post("/create")
def create_book(req: Request, payload: BookCreateIn):
    db = _get_db(req)

    book_id = f"book_{payload.title.lower().replace(' ', '-')[:24]}_{uuid4().hex[:6]}"
    book = {
        "id": book_id,
        "title": payload.title,
        "author": payload.author,
        "language": payload.language,
        "chapters": [c.model_dump() for c in payload.chapters],
    }

    db[book_id] = book
    # PERSISTENZA SUBITO
    storage.save_books_to_disk(db)

    return {
        "ok": True,
        "book_id": book_id,
        **book,
    }

@router.delete("/{book_id}")
def delete_book(req: Request, book_id: str):
    db = _get_db(req)
    if book_id not in db:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    del db[book_id]
    storage.save_books_to_disk(db)
    return {"ok": True, "deleted": book_id}
