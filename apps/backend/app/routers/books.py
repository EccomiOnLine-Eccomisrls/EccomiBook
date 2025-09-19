# apps/backend/app/routers/books.py
from fastapi import APIRouter, HTTPException, Request, Body
from pydantic import BaseModel
from typing import List, Dict
import uuid

from .. import storage

router = APIRouter()


# ------------------ MODELS ------------------
class Chapter(BaseModel):
    id: str
    title: str
    content: str = ""


class Book(BaseModel):
    id: str
    title: str
    author: str
    language: str = "it"
    chapters: List[Chapter] = []


class BookCreateIn(BaseModel):
    title: str
    author: str
    language: str = "it"
    chapters: List[Dict] = []


# ------------------ ROUTES ------------------
@router.get("/books")
def list_books(request: Request) -> Dict[str, Book]:
    return request.app.state.books or {}


@router.post("/books/create")
def create_book(request: Request, payload: BookCreateIn = Body(...)) -> Book:
    books = request.app.state.books

    # Genera ID univoco
    book_id = f"book_{payload.title.lower().replace(' ', '-')}_{uuid.uuid4().hex[:6]}"
    new_book = Book(
        id=book_id,
        title=payload.title,
        author=payload.author,
        language=payload.language,
        chapters=[],
    )

    # Salva in memoria
    books[book_id] = new_book.dict()

    # Persistenza su disco
    storage.save_books_to_disk(books)

    return new_book


@router.delete("/books/{book_id}")
def delete_book(book_id: str, request: Request):
    books = request.app.state.books
    if book_id not in books:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    del books[book_id]
    storage.save_books_to_disk(books)
    return {"ok": True}
