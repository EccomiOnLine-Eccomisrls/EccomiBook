from fastapi import APIRouter, HTTPException, Body, Request, Header, Depends
from pydantic import BaseModel
import uuid
import re
from typing import Any

from ..settings import get_settings
from .. import storage
from ..deps import get_current_user
from ..plans import PLANS

router = APIRouter()

class BookIn(BaseModel):
    title: str
    author: str | None = None
    abstract: str | None = None
    description: str | None = None
    genre: str | None = None
    language: str = "it"
    plan: str | None = None
    chapters: list[dict[str, Any]] = []

def slugify(text: str) -> str:
    """Crea slug leggibile dal titolo."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")

@router.get("/books", tags=["books"], summary="Lista libri (Libreria)")
def list_books(request: Request, user=Depends(get_current_user)):
    # In questo MVP mostriamo tutti i libri: se vorrai, filtra per utente
    books_db: dict = request.app.state.books
    # ritorna come lista ordinata per titolo
    out = sorted(books_db.values(), key=lambda b: b.get("title","").lower())
    return {"items": out, "count": len(out)}

@router.post("/books/create", tags=["books"], summary="Crea libro")
def create_book(
    request: Request,
    payload: BookIn = Body(...),
    x_api_key: str | None = Header(default=None),
    user=Depends(get_current_user),
):
    # Controllo piano utente
    rules = PLANS.get((user.plan or "START").upper(), PLANS["START"])
    if not rules.allow_books:
        raise HTTPException(status_code=403, detail="Il tuo piano non consente la creazione di libri")

    # Genera ID libro leggibile
    slug = slugify(payload.title) or "senza-titolo"
    random_part = uuid.uuid4().hex[:6]
    book_id = f"book_{slug}_{random_part}"

    # Salva in memoria
    books_db: dict = request.app.state.books
    books_db[book_id] = {
        "id": book_id,
        "title": payload.title,
        "author": payload.author or "EccomiBook",
        "abstract": payload.abstract,
        "description": payload.description,
        "genre": payload.genre,
        "language": payload.language,
        "plan": payload.plan or user.plan,
        "chapters": payload.chapters or [],
    }

    # Persisti subito su disco
    storage.save_books_to_disk(books_db)

    return {"book_id": book_id, "title": payload.title, "chapters_count": len(payload.chapters or [])}

@router.get("/books/{book_id}", tags=["books"], summary="Dettaglio libro")
def get_book(book_id: str, request: Request, user=Depends(get_current_user)):
    books_db: dict = request.app.state.books
    book = books_db.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    return book
