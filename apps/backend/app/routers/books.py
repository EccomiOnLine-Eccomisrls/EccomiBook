# apps/backend/app/routers/books.py
from fastapi import APIRouter, HTTPException, Body, Request, Path
from pydantic import BaseModel, Field
import uuid
import re
from datetime import datetime

from .. import storage

router = APIRouter()


# ------------------------------ Models ---------------------------------

class BookIn(BaseModel):
    title: str = Field(..., min_length=1)
    author: str | None = None
    abstract: str | None = None
    description: str | None = None
    genre: str | None = None
    language: str = "it"
    plan: str | None = None
    chapters: list[dict] = []


class ChapterIn(BaseModel):
    title: str | None = None
    content: str = Field(..., min_length=1)


# ------------------------------ Utils ----------------------------------

def _slugify(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


# ------------------------------ Routes ---------------------------------

@router.get("/books", tags=["books"])
def list_books(request: Request):
    """
    Restituisce la libreria intera (array di libri).
    """
    books_db: dict = request.app.state.books
    # ordina per updated_at desc se presente
    def _sort_key(b: dict):
        return b.get("updated_at") or b.get("created_at") or ""
    out = list(books_db.values())
    out.sort(key=_sort_key, reverse=True)
    return out


@router.post("/books/create", tags=["books"])
def create_book(
    request: Request,
    payload: BookIn = Body(...),
):
    """
    Crea un libro base. (Nessuna auth in questa MVP.)
    """
    books_db: dict = request.app.state.books

    slug = _slugify(payload.title) or "senza-titolo"
    random_part = uuid.uuid4().hex[:6]
    book_id = f"book_{slug}_{random_part}"

    now = _now_iso()
    book = {
        "id": book_id,
        "title": payload.title,
        "author": payload.author,
        "abstract": payload.abstract,
        "description": payload.description,
        "genre": payload.genre,
        "language": payload.language,
        "plan": payload.plan,
        "chapters": payload.chapters or [],
        "created_at": now,
        "updated_at": now,
    }

    books_db[book_id] = book
    storage.save_books_to_disk(books_db)  # persistiamo subito

    return {
        "book_id": book_id,
        "title": payload.title,
        "chapters_count": len(book["chapters"]),
        "created_at": now,
    }


@router.put("/books/{book_id}/chapters/{chapter_id}", tags=["books"])
def upsert_chapter(
    request: Request,
    book_id: str = Path(..., description="ID del libro"),
    chapter_id: str = Path(..., description="ID del capitolo (es. ch_0001)"),
    payload: ChapterIn = Body(...),
):
    """
    Crea/Aggiorna un capitolo:
    - salva il file su disco: /chapters/<book_id>/<chapter_id>.md
    - aggiorna l'entry del capitolo nel libro (title, path, updated_at)
    """
    books_db: dict = request.app.state.books
    book = books_db.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    # 1) Salva il contenuto a disco
    rel_path = storage.save_chapter_file(book_id, chapter_id, payload.content or "")

    # 2) Aggiorna la entry capitolo nel libro
    chapters = book.setdefault("chapters", [])
    found = None
    for ch in chapters:
        if ch.get("id") == chapter_id:
            found = ch
            break

    now = _now_iso()
    if found:
        found["title"] = payload.title or found.get("title")
        found["path"] = rel_path
        found["updated_at"] = now
    else:
        chapters.append({
            "id": chapter_id,
            "title": payload.title or f"Capitolo {chapter_id}",
            "path": rel_path,
            "created_at": now,
            "updated_at": now,
        })

    book["updated_at"] = now
    books_db[book_id] = book
    storage.save_books_to_disk(books_db)

    return {
        "ok": True,
        "book_id": book_id,
        "chapter_id": chapter_id,
        "path": rel_path,
        "updated_at": now,
    }
