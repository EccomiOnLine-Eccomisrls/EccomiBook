# apps/backend/app/routers/books.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Body, Response
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
from fpdf import FPDF
import re

from app import storage

router = APIRouter()

# --------- Schemi ---------
class BookIn(BaseModel):
    title: str
    author: Optional[str] = None
    abstract: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    language: str = "it"
    plan: Optional[str] = None
    chapters: List[Dict[str, Any]] = Field(default_factory=list)

class BookUpdateIn(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    abstract: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    language: Optional[str] = None
    plan: Optional[str] = None

class ReorderIn(BaseModel):
    order: List[str]  # lista di chapter.id nel nuovo ordine

class ChapterCreateIn(BaseModel):
    title: Optional[str] = "Nuovo capitolo"
    content: Optional[str] = ""
    language: Optional[str] = None

class ChapterUpdateIn(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    language: Optional[str] = None

# --------- Helpers ---------
def _ensure_chapters(book: Dict[str, Any]) -> None:
    if not book.get("chapters"):
        book["chapters"] = []

def _ensure_first_chapter(book: Dict[str, Any]) -> None:
    _ensure_chapters(book)
    if not book["chapters"]:
        book["chapters"].append({
            "id": "ch_0001",
            "title": "Capitolo 1",
            "content": "",
            "language": book.get("language", "it")
        })

def _next_chapter_id(book: Dict[str, Any]) -> str:
    _ensure_chapters(book)
    max_n = 0
    for ch in book["chapters"]:
        m = re.match(r"^ch_(\d{4})$", str(ch.get("id", "")))
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"ch_{(max_n + 1):04d}"

def _find_chapter_index(book: Dict[str, Any], chapter_id: str) -> int:
    _ensure_chapters(book)
    for i, ch in enumerate(book["chapters"]):
        if ch.get("id") == chapter_id:
            return i
    raise HTTPException(status_code=404, detail="Capitolo non trovato")

# --------- Endpoints libri ---------
@router.get("/books")
def list_books():
    return storage.load_books()

@router.get("/books/{book_id}")
def get_book(book_id: str):
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    return b

@router.post("/books", status_code=201)
def create_book(payload: BookIn):
    now = datetime.utcnow().isoformat()
    new_id = f"book_{int(datetime.utcnow().timestamp())}"
    book = payload.dict()
    book.update({"id": new_id, "created_at": now, "updated_at": now})
    _ensure_chapters(book)  # solo array vuoto, nessun capitolo
    storage.persist_book(book)
    return book

@router.patch("/books/{book_id}")
def update_book(book_id: str, payload: BookUpdateIn):
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    data = payload.dict(exclude_unset=True)
    for k, v in data.items():
        b[k] = v
    b["updated_at"] = datetime.utcnow().isoformat()
    storage.persist_book(b)
    return b

@router.delete("/books/{book_id}", status_code=204, summary="Delete Book")
def delete_book(book_id: str):
    """
    Elimina il libro con ID book_id. Ritorna 204 se ok, 404 se non trovato.
    """
    # Se il modulo storage ha una funzione dedicata, usala:
    if hasattr(storage, "delete_book"):
        ok = storage.delete_book(book_id)  # deve restituire True/False
        if not ok:
            raise HTTPException(status_code=404, detail="Libro non trovato")
        return Response(status_code=204)

    # Fallback generico: carica tutti i libri, rimuovi quello richiesto, salva
    books = storage.load_books()
    # NB: supporto sia "id" sia "book_id"
    new_books = [
        b for b in books
        if (b.get("id") or b.get("book_id")) != book_id
    ]
    if len(new_books) == len(books):
        raise HTTPException(status_code=404, detail="Libro non trovato")

    # Salva la lista aggiornata (adatta al tuo storage)
    if hasattr(storage, "save_books"):
        storage.save_books(new_books)
    elif hasattr(storage, "persist_books"):
        storage.persist_books(new_books)  # se esiste equivalente
    else:
        # Se non hai una funzione per salvare l'intera lista, creane una in storage.py
        raise RuntimeError("Aggiungi save_books(new_books) nel modulo storage.")

    return Response(status_code=204)

# --------- Endpoints capitoli ---------
@router.post("/books/{book_id}/chapters", status_code=201)
def create_chapter(book_id: str, payload: ChapterCreateIn = Body(default=ChapterCreateIn())):
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    _ensure_chapters(b)
    new_id = _next_chapter_id(b)
    chapter = {
        "id": new_id,
        "title": payload.title or "Nuovo capitolo",
        "content": payload.content or "",
        "language": payload.language or b.get("language", "it")
    }
    b["chapters"].append(chapter)
    b["updated_at"] = datetime.utcnow().isoformat()
    storage.persist_book(b)
    return {"ok": True, "chapter": chapter, "count": len(b["chapters"])}

@router.get("/books/{book_id}/chapters/{chapter_id}")
def get_chapter(book_id: str, chapter_id: str):
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    ci = _find_chapter_index(b, chapter_id)
    return b["chapters"][ci]

# ==== EXPORT CAPITOLO: Markdown ====
@router.get("/books/{book_id}/chapters/{chapter_id}.md", summary="Export Chapter MD")
def export_chapter_md(book_id: str, chapter_id: str):
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    ch = next((c for c in b.get("chapters", []) if str(c.get("id")) == chapter_id), None)
    if not ch:
        raise HTTPException(status_code=404, detail="Capitolo non trovato")

    title = (ch.get("title") or chapter_id).strip()
    body  = str(ch.get("content") or "")
    md    = f"# {title}\n\n{body}"

    headers = {
        "Content-Disposition": f'attachment; filename="{book_id}_{chapter_id}.md"'
    }
    return Response(content=md, media_type="text/markdown; charset=utf-8", headers=headers)


# ==== EXPORT CAPITOLO: TXT ====
@router.get("/books/{book_id}/chapters/{chapter_id}.txt", summary="Export Chapter TXT")
def export_chapter_txt(book_id: str, chapter_id: str):
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    ch = next((c for c in b.get("chapters", []) if str(c.get("id")) == chapter_id), None)
    if not ch:
        raise HTTPException(status_code=404, detail="Capitolo non trovato")

    title = (ch.get("title") or chapter_id).strip()
    body  = str(ch.get("content") or "")
    txt   = f"{title}\n\n{body}"

    headers = {
        "Content-Disposition": f'attachment; filename="{book_id}_{chapter_id}.txt"'
    }
    return Response(content=txt, media_type="text/plain; charset=utf-8", headers=headers)

@router.get("/books/{book_id}/chapters", summary="List Chapters")
def list_chapters(book_id: str):
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    return {"items": b.get("chapters", [])}

@router.get("/books/{book_id}/chapters/{chapter_id}.pdf", summary="Export Chapter (PDF)")
def export_chapter_pdf(book_id: str, chapter_id: str):
    try:
        from fpdf import FPDF
    except Exception:
        raise HTTPException(status_code=501, detail="PDF non abilitato (installare fpdf2)")

    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    for ch in b.get("chapters", []):
        if ch.get("id") == chapter_id:
            title = (ch.get("title") or chapter_id).strip()
            content = (ch.get("content") or "").replace("\r\n", "\n")

            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.multi_cell(0, 10, txt=title)
            pdf.ln(4)
            pdf.set_font("Helvetica", size=12)
            for line in content.split("\n"):
                pdf.multi_cell(0, 7, txt=line)

            pdf_bytes = pdf.output(dest="S").encode("latin1", "ignore")
            filename = f"{book_id}.{chapter_id}.pdf"
            headers = { "Content-Disposition": f'attachment; filename="{filename}"' }
            return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)

    raise HTTPException(status_code=404, detail="Capitolo non trovato")
    
@router.put("/books/{book_id}/chapters/{chapter_id}")
def update_chapter(book_id: str, chapter_id: str, payload: ChapterUpdateIn = Body(...)):
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    _ensure_chapters(b)
    ci = _find_chapter_index(b, chapter_id)
    ch = b["chapters"][ci]

    data = payload.dict(exclude_unset=True)
    if data.get("title") is not None:
        ch["title"] = data["title"]
    if data.get("content") is not None:
        ch["content"] = data["content"]
    if data.get("language") is not None:
        ch["language"] = data["language"]

    b["chapters"][ci] = ch
    b["updated_at"] = datetime.utcnow().isoformat()
    storage.persist_book(b)
    return {"ok": True, "chapter": ch}

@router.delete("/books/{book_id}/chapters/{chapter_id}")
def delete_chapter(book_id: str, chapter_id: str):
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    _ensure_chapters(b)
    ci = _find_chapter_index(b, chapter_id)
    removed = b["chapters"].pop(ci)

    # ❌ rimosso: non ricreiamo più un capitolo se array vuoto

    b["updated_at"] = datetime.utcnow().isoformat()
    storage.persist_book(b)
    return {"ok": True, "removed": removed["id"], "count": len(b["chapters"])}

@router.post("/books/{book_id}/chapters/reorder")
def reorder_chapters(book_id: str, payload: ReorderIn = Body(...)):
    try:
        updated = storage.reorder_chapters(book_id, payload.order)
        return {"ok": True, "book": updated, "count": len(updated.get("chapters", []))}
    except ValueError:
        raise HTTPException(status_code=404, detail="Libro non trovato")
