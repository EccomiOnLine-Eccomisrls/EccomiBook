from fastapi import APIRouter, HTTPException, Body, Request
from pydantic import BaseModel
import uuid, re

router = APIRouter()

class BookIn(BaseModel):
    title: str
    author: str | None = None
    abstract: str | None = None
    description: str | None = None
    genre: str | None = None
    language: str = "it"
    chapters: list[dict] = []

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")

@router.post("/books/create", tags=["books"])
def create_book(request: Request, payload: BookIn = Body(...)):
    slug = slugify(payload.title) or "senza-titolo"
    random_part = uuid.uuid4().hex[:6]
    book_id = f"book_{slug}_{random_part}"

    books_db = request.app.state.books
    books_db[book_id] = {
        "id": book_id,
        "title": payload.title,
        "author": payload.author,
        "abstract": payload.abstract,
        "description": payload.description,
        "genre": payload.genre,
        "language": payload.language,
        "chapters": payload.chapters,
    }

    return {"book_id": book_id, "title": payload.title, "chapters_count": len(payload.chapters)}
