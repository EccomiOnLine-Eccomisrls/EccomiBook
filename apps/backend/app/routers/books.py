from fastapi import APIRouter, HTTPException, Body, Request, Response
from fastapi.responses import PlainTextResponse, FileResponse
from pydantic import BaseModel
import uuid
import re
from typing import Any
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

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
    return request.app.state.books

# ─────────────────────────────────────────────────────────
# Endpoints libri
# ─────────────────────────────────────────────────────────
@router.get("/books")
def list_books(request: Request):
    books_db = _books_db(request)
    return list(books_db.values())

@router.post("/books/create")
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

@router.delete("/books/{book_id}", status_code=204)
def delete_book(request: Request, book_id: str):
    books_db = _books_db(request)
    if book_id not in books_db:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    books_db.pop(book_id, None)
    storage.save_books_to_disk(books_db)
    return

# ─────────────────────────────────────────────────────────
# Capitoli: CRUD + export
# ─────────────────────────────────────────────────────────
@router.get("/books/{book_id}/chapters/{chapter_id}")
def get_chapter(book_id: str, chapter_id: str, request: Request):
    books_db = _books_db(request)
    if book_id not in books_db:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    exists, content, rel_path = storage.read_chapter_file(book_id, chapter_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Capitolo non trovato")
    return {"book_id": book_id, "chapter_id": chapter_id, "path": rel_path, "content": content, "exists": True}

@router.put("/books/{book_id}/chapters/{chapter_id}")
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

@router.delete("/books/{book_id}/chapters/{chapter_id}", status_code=204)
def delete_chapter(request: Request, book_id: str, chapter_id: str):
    books_db = _books_db(request)
    book = books_db.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    # rimuovi file
    storage.delete_chapter_file(book_id, chapter_id)

    # rimuovi voce dal libro
    chapters = book.setdefault("chapters", [])
    book["chapters"] = [ch for ch in chapters if ch.get("id") != chapter_id]
    storage.save_books_to_disk(books_db)
    return

# ---- Export MD/TXT/PDF singolo capitolo ------------------------------------
def _chapter_content_or_404(book_id: str, chapter_id: str) -> str:
    exists, content, _ = storage.read_chapter_file(book_id, chapter_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Capitolo non trovato")
    return content

@router.get("/books/{book_id}/chapters/{chapter_id}.md", response_class=PlainTextResponse)
def export_chapter_md(book_id: str, chapter_id: str):
    content = _chapter_content_or_404(book_id, chapter_id)
    headers = {"Content-Disposition": f'attachment; filename="{chapter_id}.md"'}
    return Response(content, media_type="text/markdown; charset=utf-8", headers=headers)

@router.get("/books/{book_id}/chapters/{chapter_id}.txt", response_class=PlainTextResponse)
def export_chapter_txt(book_id: str, chapter_id: str):
    content = _chapter_content_or_404(book_id, chapter_id)
    headers = {"Content-Disposition": f'attachment; filename="{chapter_id}.txt"'}
    return Response(content, media_type="text/plain; charset=utf-8", headers=headers)

@router.get("/books/{book_id}/chapters/{chapter_id}.pdf")
def export_chapter_pdf(book_id: str, chapter_id: str):
    content = _chapter_content_or_404(book_id, chapter_id)
    # crea PDF temporaneo minimale
    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf_path = Path(tmp.name)
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4
    y = height - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, chapter_id)
    y -= 24
    c.setFont("Helvetica", 11)
    for line in content.splitlines():
        if y < 40:
            c.showPage()
            y = height - 40
            c.setFont("Helvetica", 11)
        c.drawString(40, y, line[:110])
        y -= 16
    c.showPage()
    c.save()
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"{chapter_id}.pdf")
