# apps/backend/app/routers/books.py
from fastapi import APIRouter, HTTPException, Body, Request
from pydantic import BaseModel
import uuid
import re
from typing import Any

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
    chapters: list[dict] = []  # [{id, path?, ...}]


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
    books_db = _books_db(request)
    # ritorno come lista per semplicità
    return list(books_db.values())


@router.post("/books/create", tags=["books"])
def create_book(request: Request, payload: BookIn = Body(...)):
    # Genera ID leggibile
    slug = slugify(payload.title) or "senza-titolo"
    random_part = uuid.uuid4().hex[:6]
    book_id = f"book_{slug}_{random_part}"

    # Salva in memoria
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

    # Persisti su disco
    storage.save_books_to_disk(books_db)

    return {"book_id": book_id, "title": payload.title, "chapters_count": len(payload.chapters or [])}


@router.delete("/books/{book_id}", tags=["books"], status_code=204)
def delete_book(request: Request, book_id: str):
    books_db = _books_db(request)
    if book_id not in books_db:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    # Per MVP rimuoviamo solo dal "DB" (i file capitolo restano)
    books_db.pop(book_id, None)
    storage.save_books_to_disk(books_db)
    return  # 204


@router.put("/books/{book_id}/chapters/{chapter_id}", tags=["books"])
def upsert_chapter(
    request: Request,
    book_id: str,
    chapter_id: str,
    payload: ChapterUpdate = Body(...),
):
    """
    Crea/aggiorna un capitolo:
    - scrive il contenuto su disco (…/chapters/<book_id>/<chapter_id>.md)
    - registra/aggiorna l'entry nel libro (chapters[])
    """
    books_db = _books_db(request)
    book = books_db.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    # 1) Salva file su disco e ottieni path relativo (p.es. chapters/book_…/ch_0001.md)
    rel_path = storage.save_chapter_file(book_id, chapter_id, payload.content or "")

    # 2) Aggiorna o inserisce l'entry del capitolo nel libro
    chapters = book.setdefault("chapters", [])
    idx = next((i for i, ch in enumerate(chapters) if (ch.get("id") == chapter_id)), -1)
    chapter_obj = {"id": chapter_id, "path": rel_path}
    if idx >= 0:
        # aggiorna mantenendo eventuali campi extra
        chapters[idx].update(chapter_obj)
    else:
        chapters.append(chapter_obj)

    # 3) Persisti su disco tutto il "DB" libri
    storage.save_books_to_disk(books_db)

    return {"ok": True, "book_id": book_id, "chapter": chapter_obj}
