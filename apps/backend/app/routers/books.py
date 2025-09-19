# apps/backend/app/routers/books.py
from fastapi import APIRouter, HTTPException, Body, Request, Header, Depends
from pydantic import BaseModel
import uuid, re

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
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")

@router.get("/books", tags=["books"])
def list_books(request: Request, user=Depends(get_current_user)):
    """
    Ritorna tutti i libri dell'utente (MVP: nessun filtro per owner).
    """
    books_db = request.app.state.books
    # opzionale: filtra per piano/utente se vorrai
    return list(books_db.values())

@router.post("/books/create", tags=["books"])
def create_book(
    request: Request,
    payload: BookIn = Body(...),
    x_api_key: str | None = Header(default=None),
    user=Depends(get_current_user),
):
    # Regole piano
    rules = PLANS.get((user.plan or "START").upper(), PLANS["START"])
    if not rules.allow_books:
        raise HTTPException(status_code=403, detail="Il tuo piano non consente la creazione di libri")

    # ID leggibile
    slug = slugify(payload.title) or "senza-titolo"
    random_part = uuid.uuid4().hex[:6]
    book_id = f"book_{slug}_{random_part}"

    # Salva in memoria
    books_db = request.app.state.books
    books_db[book_id] = {
        "id": book_id,
        "title": payload.title or "",
        "author": payload.author or "",
        "abstract": payload.abstract or "",
        "description": payload.description or "",
        "genre": payload.genre or "",
        "language": payload.language or "it",
        "plan": payload.plan or (user.plan or "START"),
        "chapters": payload.chapters or [],
    }

    # 👉 Salva SUBITO su disco (persistenza post-deploy)
    storage.save_books_to_disk(books_db)

    return {"book_id": book_id, "title": payload.title, "chapters_count": len(payload.chapters or [])}

@router.put("/books/{book_id}/chapters/{chapter_id}", tags=["books"])
def update_chapter(
    request: Request,
    book_id: str,
    chapter_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    """
    Aggiorna/salva un capitolo. MVP: accetta { "content": "<testo>" } e
    salva anche su file markdown sul disco persistente.
    """
    books_db = request.app.state.books
    book = books_db.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    content = (body or {}).get("content", "")
    # salva file capitolo
    rel_path = storage.save_chapter_file(book_id, chapter_id, content)

    # aggiorna struttura libro (MVP: chapters come array di dict)
    # se esiste, aggiorno; se no, aggiungo.
    if "chapters" not in book or not isinstance(book["chapters"], list):
        book["chapters"] = []
    found = False
    for ch in book["chapters"]:
        if ch.get("id") == chapter_id:
            ch["path"] = rel_path
            found = True
            break
    if not found:
        book["chapters"].append({"id": chapter_id, "path": rel_path})

    # persisti DB libri
    storage.save_books_to_disk(books_db)

    return {"ok": True, "book_id": book_id, "chapter_id": chapter_id, "path": rel_path}
