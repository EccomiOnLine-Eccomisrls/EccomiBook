from fastapi import APIRouter, Header, HTTPException, Request, Body, Query
from typing import Dict, Any, Literal
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from pathlib import Path
import time

from ..models import GenChapterIn, GenChapterOut
from ..settings import get_settings
from .. import storage

router = APIRouter()


def _auth_or_403(x_api_key: str | None):
    settings = get_settings()
    if settings.x_api_key and x_api_key != settings.x_api_key:
        raise HTTPException(status_code=403, detail="Chiave API non valida")


@router.post(
    "/generate/chapter",
    summary="Generate Chapter",
    response_model=GenChapterOut,
)
def generate_chapter(
    request: Request,
    payload: GenChapterIn = Body(...),
    x_api_key: str | None = Header(default=None),
):
    _auth_or_403(x_api_key)

    # mock “AI”: crea testo semplice usando prompt/outline
    txt_lines: list[str] = []
    txt_lines.append(f"# {payload.title}".strip())
    if payload.outline:
        txt_lines.append("")
        txt_lines.append(f"Outline: {payload.outline}")
    if payload.prompt:
        txt_lines.append("")
        txt_lines.append(payload.prompt)

    content = "\n".join(txt_lines)

    # opzionale: allega al libro
    if payload.book_id:
        books: Dict[str, Dict[str, Any]] = request.app.state.books
        book_id = payload.book_id
        if book_id not in books:
            raise HTTPException(status_code=404, detail="Libro non trovato")
        idx = len(books[book_id]["chapters"]) + 1
        ch_id = f"ch_{idx:08x}"
        books[book_id]["chapters"].append(
            {"id": ch_id, "title": payload.title, "prompt": payload.prompt, "outline": payload.outline or ""}
        )
        return GenChapterOut(chapter_id=ch_id, title=payload.title, content=content)

    # se non legato a libro
    return GenChapterOut(chapter_id=None, title=payload.title, content=content)


@router.get(
    "/generate/export/book/{book_id}",
    summary="Export Book",
)
def export_book(
    request: Request,
    book_id: str,
    format: Literal["pdf", "docx", "epub"] = Query("pdf"),
    x_api_key: str | None = Header(default=None),
):
    _auth_or_403(x_api_key)
    books: Dict[str, Dict[str, Any]] = request.app.state.books
    if book_id not in books:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    book = books[book_id]
    # Supporto MVP: solo PDF reale; docx/epub -> placeholder
    filename = f"{book_id}.{format}"
    if format == "pdf":
        out_path: Path = storage.file_path(filename)
        c = canvas.Canvas(str(out_path), pagesize=A4)
        width, height = A4
        y = height - 40
        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, y, book["title"])
        y -= 24
        c.setFont("Helvetica", 11)
        c.drawString(40, y, f"Autore: {book['author']}  •  Lingua: {book['language']}  •  Genere: {book['genre']}")
        y -= 30
        c.setFont("Helvetica", 10)
        c.drawString(40, y, book.get("description", "")[:1000])
        y -= 30

        for i, ch in enumerate(book["chapters"], start=1):
            if y < 80:
                c.showPage()
                y = height - 40
                c.setFont("Helvetica", 10)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(40, y, f"{i}. {ch['title']}")
            y -= 18
            c.setFont("Helvetica", 10)
            body = (ch.get("outline") or ch.get("prompt") or "").replace("\n", " ")
            for segment in [body[i : i + 90] for i in range(0, len(body), 90)]:
                if y < 60:
                    c.showPage()
                    y = height - 40
                    c.setFont("Helvetica", 10)
                c.drawString(50, y, segment)
                y -= 14

            y -= 10

        c.showPage()
        c.save()
    else:
        # placeholder: crea un file “vuoto” col nome richiesto
        storage.file_path(filename).write_text(f"{format.upper()} export placeholder for {book_id}\n")

    url = storage.public_url(filename)
    return {
        "ok": True,
        "book_id": book_id,
        "format": format,
        "file_name": filename,
        "url": url,
        "chapters": len(book["chapters"]),
        "generated_at": int(time.time()),
    }
