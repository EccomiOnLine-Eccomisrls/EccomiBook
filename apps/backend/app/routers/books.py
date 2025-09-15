from fastapi import APIRouter, Depends, HTTPException, Path
from typing import List
from app.ai import (
    current_caps,
    ensure_can_create_book,
    ensure_can_add_chapter,
)
from app.models import BookCreate, BookOut, ChapterCreate, ChapterOut
from app import storage

router = APIRouter(prefix="", tags=["Books"])


@router.get("/books", response_model=List[BookOut])
def list_books():
    """Elenco libri in memoria."""
    return storage.list_books()


@router.post("/books", response_model=BookOut)
def create_book(body: BookCreate, caps=Depends(current_caps)):
    """
    Crea un nuovo libro.
    - Applica i limiti del piano (libri/mese).
    - Incrementa il contatore libri all’avvenuta creazione.
    """
    ensure_can_create_book(caps)
    book = storage.create_book(body)
    # contatore “consumo” piano
    storage.inc_book(caps.user_id)
    return book


@router.post("/books/{book_id}/chapters", response_model=ChapterOut)
def add_chapter(
    book_id: str = Path(..., description="ID del libro"),
    body: ChapterCreate = ...,
    caps=Depends(current_caps),
):
    """
    Aggiunge un capitolo a un libro.
    - Applica i limiti del piano (capitoli/giorno).
    - Incrementa il contatore capitoli all’avvenuta creazione.
    """
    # verifica che il libro esista
    if not storage.get_book(book_id):
        raise HTTPException(status_code=404, detail="Libro non trovato")

    ensure_can_add_chapter(caps)
    ch = storage.add_chapter(book_id, body)
    storage.inc_chapter(caps.user_id)
    return ch


@router.put("/books/{book_id}/chapters/{chapter_id}", response_model=ChapterOut)
def update_chapter(
    book_id: str,
    chapter_id: str,
    body: ChapterCreate,
    caps=Depends(current_caps),
):
    """
    Aggiorna titolo/prompt/outline di un capitolo esistente.
    (Non consuma il limite perché è editing.)
    """
    if not storage.get_book(book_id):
        raise HTTPException(status_code=404, detail="Libro non trovato")

    ch = storage.update_chapter(book_id, chapter_id, body)
    if not ch:
        raise HTTPException(status_code=404, detail="Capitolo non trovato")
    return ch
