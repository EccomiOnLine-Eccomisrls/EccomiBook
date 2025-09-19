# apps/backend/app/routers/books.py
from fastapi import APIRouter, HTTPException, Body, Request, Header, Depends
from pydantic import BaseModel
import uuid
import re

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
    chapters: list[dict] = []


def slugify(text: str) -> str:
    """Crea slug leggibile dal titolo."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


@router.post("/books/create", tags=["books"])
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
    books_db = request.app.state.books
    books_db[book_id] = {
        "id": book_id,
        "title": payload.title,
        "author": payload.author,
        "abstract": payload.abstract,
        "description": payload.description,
        "genre": payload.genre,
        "language": payload.language,
        "plan": payload.plan or user.plan,
        "chapters": payload.chapters,
    }

    return {"book_id": book_id, "title": payload.title, "chapters_count": len(payload.chapters)}


# 🔥 Nuovo endpoint: aggiorna un capitolo esistente
@router.put("/books/{book_id}/chapters/{chapter_id}", tags=["books"])
def update_chapter(
    book_id: str,
    chapter_id: str,
    request: Request,
    payload: dict = Body(...),
    x_api_key: str | None = Header(default=None),
    user=Depends(get_current_user),
):
    books_db = request.app.state.books

    if book_id not in books_db:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    chapters = books_db[book_id].get("chapters", [])
    for ch in chapters:
        if ch.get("id") == chapter_id:
            # Aggiorna i campi passati
            if "title" in payload:
                ch["title"] = payload["title"]
            if "content" in payload:
                ch["content"] = payload["content"]
            if "outline" in payload:
                ch["outline"] = payload["outline"]

            return {"ok": True, "chapter": ch}

    raise HTTPException(status_code=404, detail="Capitolo non trovato")
