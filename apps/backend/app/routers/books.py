# apps/backend/app/routers/books.py
from fastapi import APIRouter, HTTPException, Body, Request
from pydantic import BaseModel
import uuid
import re

from .. import storage  # non usato qui, ma lasciato se serve altrove
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
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


@router.get("/books", tags=["books"])
def list_books(request: Request):
    """
    MVP: endpoint pubblico (no API key).
    Restituisce l'elenco libri presenti in memoria.
    """
    books_db = request.app.state.books
    # Ritorna piccoli campi utili al frontend
    return [
        {
            "id": b["id"],
            "title": b.get("title") or "Senza titolo",
            "author": b.get("author") or "",
            "chapters_count": len(b.get("chapters") or []),
        }
        for b in books_db.values()
    ]


@router.post("/books/create", tags=["books"])
def create_book(request: Request, payload: BookIn = Body(...)):
    """
    MVP: endpoint pubblico (no API key).
    Usa sempre il piano START per i limiti.
    """
    # Regole piano START (niente auth)
    rules = PLANS.get("START", None)
    if not rules:
        raise HTTPException(status_code=500, detail="Configurazione piani non valida")

    # Genera ID leggibile
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
        "plan": payload.plan or "START",
        "chapters": payload.chapters or [],
    }

    return {"book_id": book_id, "title": payload.title, "chapters_count": len(payload.chapters or [])}
