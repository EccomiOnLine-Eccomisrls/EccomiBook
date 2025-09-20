# apps/backend/app/routers/chapters.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from .. import storage
from datetime import datetime

router = APIRouter(prefix="/chapters", tags=["chapters"])

class ChapterSaveIn(BaseModel):
    book_id: str
    chapter_id: str
    content: str

@router.post("/save")
def save_chapter(req: Request, payload: ChapterSaveIn):
    app = req.app
    books: dict = getattr(app.state, "books", {})

    book = books.get(payload.book_id)
    if not book:
      # crea scheletro se il book esiste a filesystem ma non in memoria (caso raro)
      raise HTTPException(status_code=404, detail="Libro non trovato")

    # salva file su disco e ottieni percorso relativo
    rel_path = storage.save_chapter_file(payload.book_id, payload.chapter_id, payload.content)

    # aggiorna metadati nel "DB" in memoria
    chapters = book.setdefault("chapters", [])
    found = False
    for ch in chapters:
        if ch.get("id") == payload.chapter_id:
            ch["path"] = rel_path
            ch["updated_at"] = datetime.utcnow().isoformat() + "Z"
            found = True
            break
    if not found:
        chapters.append({
            "id": payload.chapter_id,
            "title": payload.chapter_id,
            "path": rel_path,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        })

    # persistenza su disco del "DB"
    storage.save_books_to_disk(books)

    return {
        "ok": True,
        "book_id": payload.book_id,
        "chapter_id": payload.chapter_id,
        "path": rel_path,
    }

@router.get("/{book_id}/{chapter_id}")
def read_chapter(book_id: str, chapter_id: str):
    try:
        content = storage.read_chapter_file(book_id, chapter_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Capitolo non trovato")
    return {"book_id": book_id, "chapter_id": chapter_id, "content": content}
