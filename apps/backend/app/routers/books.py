from fastapi import APIRouter, Header, HTTPException, Request, Body, Path
from typing import Dict, Any, List

from ..models import BookCreate, ChapterCreate, BookOut, ChapterOut
from ..settings import get_settings

router = APIRouter()


def _auth_or_403(x_api_key: str | None):
    settings = get_settings()
    if settings.x_api_key and x_api_key != settings.x_api_key:
        raise HTTPException(status_code=403, detail="Chiave API non valida")


@router.get("/books", summary="List Books", response_model=List[BookOut])
def list_books(request: Request):
    books: Dict[str, Dict[str, Any]] = request.app.state.books
    return [BookOut(**b) for b in books.values()]


@router.post("/books", summary="Create Book", response_model=BookOut)
def create_book(
    request: Request,
    payload: BookCreate = Body(...),
    x_api_key: str | None = Header(default=None),
):
    _auth_or_403(x_api_key)
    books: Dict[str, Dict[str, Any]] = request.app.state.books

    # ID incrementale semplice
    request.app.state.counters["books"] += 1
    num = request.app.state.counters["books"]
    book_id = f"book_{num:07x}"

    book: Dict[str, Any] = {
        "id": book_id,
        "title": payload.title,
        "author": payload.author,
        "language": payload.language,
        "genre": payload.genre,
        "description": payload.description,
        "abstract": payload.abstract or None,
        "plan": payload.plan,
        "chapters": [],
    }
    books[book_id] = book
    return BookOut(**book)


@router.post(
    "/books/{book_id}/chapters",
    summary="Add Chapter",
    response_model=ChapterOut,
)
def add_chapter(
    request: Request,
    book_id: str = Path(..., description="ID del libro"),
    payload: ChapterCreate = Body(...),
    x_api_key: str | None = Header(default=None),
):
    _auth_or_403(x_api_key)
    books: Dict[str, Dict[str, Any]] = request.app.state.books
    if book_id not in books:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    idx = len(books[book_id]["chapters"]) + 1
    ch_id = f"ch_{idx:08x}"

    chapter = {
        "id": ch_id,
        "title": payload.title,
        "prompt": payload.prompt,
        "outline": payload.outline or "",
    }
    books[book_id]["chapters"].append(chapter)
    return ChapterOut(**chapter)


@router.put(
    "/books/{book_id}/chapters/{chapter_id}",
    summary="Update Chapter",
    response_model=ChapterOut,
)
def update_chapter(
    request: Request,
    book_id: str,
    chapter_id: str,
    payload: ChapterCreate = Body(...),
    x_api_key: str | None = Header(default=None),
):
    _auth_or_403(x_api_key)
    books: Dict[str, Dict[str, Any]] = request.app.state.books
    if book_id not in books:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    chapters = books[book_id]["chapters"]
    for ch in chapters:
        if ch["id"] == chapter_id:
            ch["title"] = payload.title
            ch["prompt"] = payload.prompt
            ch["outline"] = payload.outline or ch.get("outline", "")
            return ChapterOut(**ch)

    raise HTTPException(status_code=404, detail="Capitolo non trovato")
