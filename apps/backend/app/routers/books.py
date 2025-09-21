# apps/backend/app/routers/books.py
from fastapi import APIRouter, HTTPException, Body, Request, Response
from pydantic import BaseModel
import uuid
import re
from typing import Any
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from io import BytesIO

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
    chapters: list[dict] = []  # [{id, path?, title?, updated_at?}]

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

def _get_book_or_404(request: Request, book_id: str) -> dict[str, Any]:
    books_db = _books_db(request)
    book = books_db.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    return book

# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────
@router.get("/books", tags=["books"])
def list_books(request: Request):
    books_db = _books_db(request)
    return list(books_db.values())

@router.get("/books/{book_id}", tags=["books"])
def get_book(request: Request, book_id: str):
    return _get_book_or_404(request, book_id)

@router.post("/books/create", tags=["books"])
def create_book(request: Request, payload: BookIn = Body(...)):
    slug = slugify(payload.title) or "senza-titolo"
    random_part = uuid.uuid4().hex[:6]
    book_id = f"book_{slug}_{random_part}"

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

    storage.save_books_to_disk(books_db)
    return {"book_id": book_id, "title": payload.title, "chapters_count": len(payload.chapters or [])}

@router.delete("/books/{book_id}", tags=["books"], status_code=204)
def delete_book(request: Request, book_id: str):
    books_db = _books_db(request)
    if book_id not in books_db:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    books_db.pop(book_id, None)
    storage.save_books_to_disk(books_db)
    return

# ── CAPITOLI: lista
@router.get("/books/{book_id}/chapters", tags=["books"])
def list_chapters(request: Request, book_id: str):
    book = _get_book_or_404(request, book_id)
    return book.get("chapters", [])

# ── CAPITOLI: lettura
@router.get("/books/{book_id}/chapters/{chapter_id}", tags=["books"])
def get_chapter(request: Request, book_id: str, chapter_id: str):
    _get_book_or_404(request, book_id)
    exists, content, rel_path = storage.read_chapter_file(book_id, chapter_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Capitolo non trovato")
    return {"book_id": book_id, "chapter_id": chapter_id, "path": rel_path, "content": content, "exists": True}

# ── CAPITOLI: creazione/aggiornamento
@router.put("/books/{book_id}/chapters/{chapter_id}", tags=["books"])
def upsert_chapter(
    request: Request,
    book_id: str,
    chapter_id: str,
    payload: ChapterUpdate = Body(...),
):
    books_db = _books_db(request)
    book = books_db.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    rel_path = storage.save_chapter_file(book_id, chapter_id, payload.content or "")

    chapters = book.setdefault("chapters", [])
    now = datetime.utcnow().isoformat() + "Z"
    idx = next((i for i, ch in enumerate(chapters) if (ch.get("id") == chapter_id)), -1)

    if idx >= 0:
        chapters[idx]["path"] = rel_path
        chapters[idx]["updated_at"] = now
    else:
        chapters.append({
            "id": chapter_id,
            "title": chapter_id,
            "path": rel_path,
            "updated_at": now,
        })

    storage.save_books_to_disk(books_db)
    return {"ok": True, "book_id": book_id, "chapter": {"id": chapter_id, "path": rel_path, "updated_at": now}}

# ── CAPITOLI: eliminazione
@router.delete("/books/{book_id}/chapters/{chapter_id}", tags=["books"], status_code=204)
def delete_chapter(request: Request, book_id: str, chapter_id: str):
    books_db = _books_db(request)
    book = books_db.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    # rimuovi dal file system (best-effort)
    storage.delete_chapter_file(book_id, chapter_id)

    # rimuovi dal "DB"
    chapters = book.get("chapters", [])
    book["chapters"] = [c for c in chapters if c.get("id") != chapter_id]
    storage.save_books_to_disk(books_db)
    return

# ── CAPITOLI: export TXT/MD/PDF
@router.get("/books/{book_id}/chapters/{chapter_id}/export", tags=["books"])
def export_chapter(request: Request, book_id: str, chapter_id: str, fmt: str = "md"):
    _get_book_or_404(request, book_id)
    exists, content, _ = storage.read_chapter_file(book_id, chapter_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Capitolo non trovato")

    filename_base = f"{book_id}_{chapter_id}"
    fmt = (fmt or "md").lower()

    if fmt in ("md", "txt"):
        media = "text/markdown" if fmt == "md" else "text/plain"
        ext = "md" if fmt == "md" else "txt"
        return Response(
            content=content,
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.{ext}"'}
        )

    if fmt == "pdf":
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        width, height = A4
        y = height - 72
        for line in (content or "").splitlines() or [""]:
            c.drawString(40, y, line[:110])
            y -= 16
            if y < 40:
                c.showPage()
                y = height - 72
        c.showPage()
        c.save()
        pdf_bytes = buf.getvalue()
        buf.close()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.pdf"'}
        )

    raise HTTPException(status_code=400, detail="Formato non supportato. Usa md|txt|pdf.")
