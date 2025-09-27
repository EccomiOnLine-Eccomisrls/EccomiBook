# apps/backend/app/routers/books.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime

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

# --------- Endpoints ---------
@router.get("/books")
def list_books():
    # ✅ niente più load_books_from_disk()
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

@router.post("/books/{book_id}/chapters/reorder")
def reorder_chapters(book_id: str, payload: ReorderIn = Body(...)):
    try:
        updated = storage.reorder_chapters(book_id, payload.order)
        return {"ok": True, "book": updated, "count": len(updated.get("chapters", []))}
    except ValueError:
        raise HTTPException(status_code=404, detail="Libro non trovato")
