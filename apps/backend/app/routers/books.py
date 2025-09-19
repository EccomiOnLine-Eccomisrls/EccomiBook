# apps/backend/app/routers/books.py
from fastapi import APIRouter, HTTPException, Body, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
import re

from .. import storage  # persistenza su disco

router = APIRouter()


# -----------------------------
# Modelli di input/output base
# -----------------------------

class BookIn(BaseModel):
    title: str
    author: Optional[str] = None
    abstract: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    language: str = "it"
    plan: Optional[str] = None
    chapters: List[Dict[str, Any]] = []  # [{id,title,outline,prompt,content,...}]

class ChapterUpdateIn(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    outline: Optional[str] = None
    prompt: Optional[str] = None


# ---------------
# Utility locali
# ---------------

def slugify(text: str) -> str:
    """Crea uno slug leggibile dal titolo."""
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


# -------------
# Endpoints
# -------------

@router.get("/books", tags=["books"])
def list_books(request: Request):
    """
    Ritorna l'elenco (compatto) dei libri presenti in memoria/disk.
    """
    books_db: Dict[str, Dict[str, Any]] = request.app.state.books
    items = []
    for bid, b in books_db.items():
        items.append({
            "id": bid,
            "title": b.get("title"),
            "author": b.get("author"),
            "language": b.get("language"),
            "chapters_count": len(b.get("chapters") or []),
        })
    return {"items": items, "count": len(items)}


@router.get("/books/{book_id}", tags=["books"])
def get_book(request: Request, book_id: str):
    """
    Dettaglio singolo libro.
    """
    books_db: Dict[str, Dict[str, Any]] = request.app.state.books
    book = books_db.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    return book


@router.post("/books/create", tags=["books"])
def create_book(
    request: Request,
    payload: BookIn = Body(...),
):
    """
    Crea un nuovo libro e lo salva subito su disco (books.json).
    Nessuna API key richiesta (MVP).
    """
    # DB in memoria
    books_db: Dict[str, Dict[str, Any]] = request.app.state.books

    # Genera ID libro leggibile
    slug = slugify(payload.title) or "senza-titolo"
    random_part = uuid.uuid4().hex[:6]
    book_id = f"book_{slug}_{random_part}"

    # Normalizza capitoli input (assicuriamo almeno un id univoco)
    norm_chapters: List[Dict[str, Any]] = []
    for ch in (payload.chapters or []):
        ch = dict(ch or {})
        if not ch.get("id"):
            ch["id"] = f"ch_{uuid.uuid4().hex[:6]}"
        if not ch.get("title"):
            ch["title"] = "Capitolo"
        norm_chapters.append(ch)

    # Scrivi su memoria
    books_db[book_id] = {
        "id": book_id,
        "title": payload.title,
        "author": payload.author,
        "abstract": payload.abstract,
        "description": payload.description,
        "genre": payload.genre,
        "language": payload.language,
        "plan": payload.plan or "START",
        "chapters": norm_chapters,
    }

    # Persistenza immediata su disco
    storage.save_books_to_disk(books_db)

    # Aggiorna contatore opzionale
    if hasattr(request.app.state, "counters"):
        request.app.state.counters["books"] = len(books_db)

    return {
        "book_id": book_id,
        "title": payload.title,
        "chapters_count": len(norm_chapters),
    }


@router.put("/books/{book_id}/chapters/{chapter_id}", tags=["books"])
def update_chapter(
    request: Request,
    book_id: str,
    chapter_id: str,
    payload: ChapterUpdateIn = Body(...),
):
    """
    Aggiorna (o crea se mancante) un capitolo del libro indicato.
    Salva subito su disco.
    """
    books_db: Dict[str, Dict[str, Any]] = request.app.state.books
    book = books_db.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    chapters: List[Dict[str, Any]] = book.get("chapters") or []

    # Trova capitolo
    idx = next((i for i, ch in enumerate(chapters) if ch.get("id") == chapter_id), None)

    if idx is None:
        # se non esiste, lo creiamo con i dati disponibili
        new_ch = {
            "id": chapter_id,
            "title": payload.title or f"Capitolo {len(chapters) + 1}",
            "content": payload.content or "",
            "outline": payload.outline,
            "prompt": payload.prompt,
        }
        chapters.append(new_ch)
    else:
        # aggiorna esistente
        ch = dict(chapters[idx])
        if payload.title is not None:
            ch["title"] = payload.title
        if payload.content is not None:
            ch["content"] = payload.content
        if payload.outline is not None:
            ch["outline"] = payload.outline
        if payload.prompt is not None:
            ch["prompt"] = payload.prompt
        chapters[idx] = ch

    # salva nel libro
    book["chapters"] = chapters
    books_db[book_id] = book

    # Persistenza immediata
    storage.save_books_to_disk(books_db)

    return {
        "book_id": book_id,
        "chapter_id": chapter_id,
        "chapters_count": len(chapters),
        "ok": True,
    }
