# apps/backend/app/routers/books.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import io

from app import storage

router = APIRouter()

# ---------------- Pydantic ----------------

class BookIn(BaseModel):
    title: str
    author: str | None = None
    abstract: str | None = None
    description: str | None = None
    genre: str | None = None
    language: str = "it"
    plan: str | None = None
    chapters: List[Dict[str, Any]] = []

class ChapterUpdate(BaseModel):
    content: str

# --------------- Helpers ------------------

def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def _book_index() -> List[Dict[str, Any]]:
    """Indice libri in memoria; se mancante, da disco."""
    books = getattr(storage, "BOOKS_CACHE", None)
    if books is None:
        # compat con main.py che può tenere l’indice in app.state
        try:
            return storage.load_books_from_disk()
        except Exception:
            return []
    return books

def _save_index(books: List[Dict[str, Any]]) -> None:
    """Salva e mantieni una cache in storage."""
    storage.save_books_to_disk(books)
    storage.BOOKS_CACHE = books

def _ensure_book_folder(book_id: str) -> Path:
    base = storage.BASE_DIR / "chapters" / book_id
    base.mkdir(parents=True, exist_ok=True)
    return base

def _read_chapter_text(book_id: str, chapter_id: str) -> str:
    base = storage.BASE_DIR / "chapters" / book_id
    for ext in (".md", ".txt"):
        p = base / f"{chapter_id}{ext}"
        if p.exists():
            try:
                return p.read_text(encoding="utf-8")
            except Exception:
                return ""
    return ""

def _write_chapter_text(book_id: str, chapter_id: str, text: str) -> Path:
    folder = _ensure_book_folder(book_id)
    p = folder / f"{chapter_id}.md"
    p.write_text(text or "", encoding="utf-8")
    return p

def _delete_chapter_files(book_id: str, chapter_id: str) -> None:
    folder = storage.BASE_DIR / "chapters" / book_id
    for ext in (".md", ".txt"):
        p = folder / f"{chapter_id}{ext}"
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
    # se vuota, elimina la cartella
    try:
        if folder.exists() and not any(folder.iterdir()):
            folder.rmdir()
    except Exception:
        pass

# --------------- API ----------------------

@router.get("/books", summary="List Books")
def list_books():
    return _book_index()

@router.post("/books/create", summary="Create Book")
def create_book(data: BookIn):
    # genera ID
    safe_title = data.title.lower().replace(" ", "-").replace("/", "-")
    book_id = f"book_{safe_title}_{datetime.utcnow().strftime('%H%M%S')}"
    # costruisci metadati
    book = {
        "id": book_id,
        "title": data.title,
        "author": data.author or "",
        "language": data.language or "it",
        "abstract": data.abstract or "",
        "description": data.description or "",
        "genre": data.genre or "",
        "plan": data.plan or "",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "chapters": [],  # importante: parte vuoto
    }

    # crea subito la cartella su disco e salva indice
    _ensure_book_folder(book_id)
    books = _book_index()
    books.append(book)
    _save_index(books)

    return {"ok": True, "book_id": book_id, "title": book["title"]}

@router.delete("/books/{book_id}", status_code=204, summary="Delete Book")
def delete_book(book_id: str):
    books = _book_index()
    before = len(books)
    books = [b for b in books if (b.get("id") or b.get("book_id")) != book_id]
    if len(books) == before:
        # se già non esiste, ok comunque
        pass
    _save_index(books)

    # elimina cartella capitoli
    folder = storage.BASE_DIR / "chapters" / book_id
    if folder.exists():
        for p in folder.glob("*"):
            try:
                p.unlink()
            except Exception:
                pass
        try:
            folder.rmdir()
        except Exception:
            pass
    return

@router.get("/books/{book_id}/chapters/{chapter_id}", summary="Get Chapter")
def get_chapter(book_id: str, chapter_id: str):
    text = _read_chapter_text(book_id, chapter_id)
    return {"book_id": book_id, "chapter_id": chapter_id, "content": text}

@router.put("/books/{book_id}/chapters/{chapter_id}", summary="Upsert Chapter")
def upsert_chapter(book_id: str, chapter_id: str, data: ChapterUpdate):
    # scrivi file
    _write_chapter_text(book_id, chapter_id, data.content or "")

    # aggiorna indice libri
    books = _book_index()
    b = next((x for x in books if (x.get("id") or x.get("book_id")) == book_id), None)
    if not b:
        # se il libro non è in indice (caso limite), crealo al volo
        b = {
            "id": book_id,
            "title": book_id,
            "author": "",
            "language": "it",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "chapters": [],
        }
        books.append(b)

    ch = b.get("chapters") or []
    # esiste?
    if not any((c.get("id") or c.get("chapter_id")) == chapter_id for c in ch):
        ch.append({
            "id": chapter_id,
            "title": chapter_id,
            "updated_at": _now_iso(),
        })
        b["chapters"] = ch
    else:
        # aggiorna timestamp
        for c in ch:
            if (c.get("id") or c.get("chapter_id")) == chapter_id:
                c["updated_at"] = _now_iso()

    b["updated_at"] = _now_iso()
    _save_index(books)

    return {"ok": True, "book_id": book_id, "chapter_id": chapter_id}

@router.delete("/books/{book_id}/chapters/{chapter_id}", status_code=204, summary="Delete Chapter")
def delete_chapter(book_id: str, chapter_id: str):
    _delete_chapter_files(book_id, chapter_id)

    books = _book_index()
    b = next((x for x in books if (x.get("id") or x.get("book_id")) == book_id), None)
    if b:
        ch = b.get("chapters") or []
        ch = [c for c in ch if (c.get("id") or c.get("chapter_id")) != chapter_id]
        b["chapters"] = ch
        b["updated_at"] = _now_iso()
        _save_index(books)
    return

# -------- Export singolo capitolo (md/txt/pdf) --------

@router.get("/books/{book_id}/chapters/{chapter_id}.md",
            response_class=PlainTextResponse,
            summary="Export Chapter Md")
def export_chapter_md(book_id: str, chapter_id: str):
    text = _read_chapter_text(book_id, chapter_id)
    return PlainTextResponse(text, media_type="text/markdown; charset=utf-8")

@router.get("/books/{book_id}/chapters/{chapter_id}.txt",
            response_class=PlainTextResponse,
            summary="Export Chapter Txt")
def export_chapter_txt(book_id: str, chapter_id: str):
    text = _read_chapter_text(book_id, chapter_id)
    return PlainTextResponse(text, media_type="text/plain; charset=utf-8")

@router.get("/books/{book_id}/chapters/{chapter_id}.pdf",
            summary="Export Chapter Pdf")
def export_chapter_pdf(book_id: str, chapter_id: str):
    # mini PDF semplice con ReportLab
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet

    text = _read_chapter_text(book_id, chapter_id)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=f"{book_id} - {chapter_id}")
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(f"{chapter_id}", styles["Heading2"]))
    story.append(Spacer(1, 12))
    for para in (text or "").split("\n\n"):
        story.append(Paragraph(para.replace("\n", "<br/>"), styles["BodyText"]))
        story.append(Spacer(1, 6))
    doc.build(story)
    pdf = buf.getvalue(); buf.close()

    headers = {"Content-Disposition": f'attachment; filename="{chapter_id}.pdf"'}
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf", headers=headers)

# --------- Rebuild libreria da DISCO ---------

@router.post("/books/refresh", summary="Rebuild library metadata from disk")
def books_refresh():
    """
    Scansiona storage/chapters/* e ricostruisce l'indice libri.
    """
    root = storage.BASE_DIR / "chapters"
    books: List[Dict[str, Any]] = []

    if root.exists():
        for book_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
            book_id = book_dir.name
            chapters: List[Dict[str, Any]] = []
            last_update = None

            for f in sorted(book_dir.glob("*.md")):
                cid = f.stem
                ts = datetime.utcfromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds") + "Z"
                chapters.append({"id": cid, "title": cid, "updated_at": ts})
                last_update = ts

            # prova anche .txt se non c’è md
            for f in sorted(book_dir.glob("*.txt")):
                cid = f.stem
                if not any(c["id"] == cid for c in chapters):
                    ts = datetime.utcfromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds") + "Z"
                    chapters.append({"id": cid, "title": cid, "updated_at": ts})
                    last_update = ts

            books.append({
                "id": book_id,
                "title": book_id,
                "author": "",
                "language": "it",
                "created_at": last_update or _now_iso(),
                "updated_at": last_update or _now_iso(),
                "chapters": chapters,
            })

    _save_index(books)
    return {"ok": True, "books": len(books)}
