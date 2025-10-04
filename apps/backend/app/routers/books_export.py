# apps/backend/app/routers/books_export.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, PlainTextResponse
from typing import List, Tuple
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from pathlib import Path
from datetime import datetime

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

from app import storage

router = APIRouter()

# ---------- Helpers ----------
def _get_book_or_404(book_id: str) -> dict:
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    return b

def _chapter_body(book: dict, ch: dict) -> str:
    """
    1) Se c'è content_path lo legge.
    2) Se manca, prova /chapters/<book_id>/<chapter_id>.txt
    3) Fallback: usa il testo dal JSON (content|text).
    """
    # 1) content_path esplicito
    content_path = ch.get("content_path")
    if content_path:
        p = Path(content_path)
        if not p.is_absolute():
            p = storage.CHAPTERS_DIR / content_path
        if p.exists():
            try:
                return p.read_text(encoding="utf-8")
            except Exception:
                pass

    # 2) convenzione su disco
    book_id = book.get("id") or book.get("book_id")
    ch_id   = ch.get("id") or ch.get("chapter_id") or ch.get("cid")
    if book_id and ch_id:
        p2 = storage.CHAPTERS_DIR / book_id / f"{ch_id}.txt"
        if p2.exists():
            try:
                return p2.read_text(encoding="utf-8")
            except Exception:
                pass

    # 3) Fallback JSON
    return ch.get("content") or ch.get("text") or ""

def _collect_book_texts(book: dict) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for ch in (book.get("chapters") or []):
        title = str(ch.get("title") or "Senza titolo")
        text  = _chapter_body(book, ch)
        out.append((title, text))
    return out

def _render_pdf(book_title: str, author: str | None, items: List[Tuple[str, str]]) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 2 * cm
    line_h = 14

    # Cover
    c.setTitle(book_title)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 5*cm, book_title)
    if author:
        c.setFont("Helvetica", 14)
        c.drawCentredString(width / 2, height - 6*cm, f"di {author}")
    c.setFont("Helvetica", 10)
    c.drawCentredString(width / 2, 2*cm, f"Generato con EccomiBook — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    c.showPage()

    # Capitoli
    for title, text in items:
        y = height - margin
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, y, title)
        y -= 20

        c.setFont("Helvetica", 11)
        max_width = width - 2*margin
        for line in _wrap_text(text, c, max_width):
            if y < margin + line_h:
                c.showPage()
                y = height - margin
                c.setFont("Helvetica", 11)
            c.drawString(margin, y, line)
            y -= line_h
        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()

def _wrap_text(text: str, canv: canvas.Canvas, max_w: float) -> List[str]:
    out: List[str] = []
    for raw_line in (text or "").splitlines():
        words = raw_line.split(" ")
        line = ""
        for w in words:
            trial = (line + " " + w).strip()
            if canv.stringWidth(trial, "Helvetica", 11) <= max_w:
                line = trial
            else:
                if line:
                    out.append(line)
                line = w
        out.append(line)
    return out

# ---------- Endpoints ----------
@router.get("/export/books/{book_id}/export/pdf")
def export_book_pdf(book_id: str):
    book = _get_book_or_404(book_id)
    items = _collect_book_texts(book)
    pdf_bytes = _render_pdf(book.get("title") or "Senza titolo", book.get("author"), items)
    filename = f"{book.get('id','book')}.pdf"
    return StreamingResponse(BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )

@router.get("/export/books/{book_id}/export/txt")
def export_book_txt(book_id: str):
    book = _get_book_or_404(book_id)
    items = _collect_book_texts(book)
    lines: List[str] = []
    lines.append((book.get("title") or "Senza titolo"))
    if book.get("author"): lines.append(f"di {book['author']}")
    lines.append("")
    for i, (title, text) in enumerate(items, start=1):
        lines.append(f"Capitolo {i}: {title}")
        lines.append(text or "")
        lines.append("")
    body = "\n".join(lines)
    filename = f"{book.get('id','book')}.txt"
    return PlainTextResponse(
        content=body,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/export/books/{book_id}/export/md")
def export_book_md(book_id: str):
    book = _get_book_or_404(book_id)
    items = _collect_book_texts(book)
    parts: List[str] = [f"# {book.get('title') or 'Senza titolo'}"]
    if book.get("author"): parts.append(f"_di {book['author']}_")
    parts.append("")
    for i, (title, text) in enumerate(items, start=1):
        parts.append(f"## Capitolo {i}: {title}")
        parts.append(text or "")
        parts.append("")
    md = "\n".join(parts)
    filename = f"{book.get('id','book')}.md"
    return PlainTextResponse(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

# ✅ accetta sia GET che POST (evita 405 su chiamate legacy)
@router.api_route("/export/books/{book_id}/export/kdp", methods=["GET", "POST"])
def export_book_kdp(book_id: str):
    """
    Restituisce un .zip con:
      - interior.pdf
      - metadata.txt
    """
    book = _get_book_or_404(book_id)
    items = _collect_book_texts(book)
    pdf_bytes = _render_pdf(book.get("title") or "Senza titolo", book.get("author"), items)

    zip_buf = BytesIO()
    with ZipFile(zip_buf, "w", ZIP_DEFLATED) as z:
        z.writestr("interior.pdf", pdf_bytes)
        meta = [
            f"Title: {book.get('title') or 'Senza titolo'}",
            f"Author: {book.get('author') or ''}",
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            f"Chapters: {len(items)}",
        ]
        z.writestr("metadata.txt", "\n".join(meta))
    zip_buf.seek(0)

    filename = f"{book.get('id','book')}_kdp.zip"
    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
@router.get("/export/books/{book_id}/chapters/{chapter_id}/export/pdf")
def export_single_chapter_pdf(book_id: str, chapter_id: str):
    book = _get_book_or_404(book_id)
    ch = next((c for c in (book.get("chapters") or []) 
               if str(c.get("id") or c.get("chapter_id") or c.get("cid")) == str(chapter_id)), None)
    if not ch:
        raise HTTPException(status_code=404, detail="Capitolo non trovato")

    title = str(ch.get("title") or "Senza titolo")
    body  = _chapter_body(book, ch)
    # _render_pdf accetta una lista di tuple (titolo, testo)
    pdf_bytes = _render_pdf(f"{book.get('title') or 'Libro'} — {title}", book.get("author"), [(title, body)])
    filename = f"{book.get('id','book')}_{chapter_id}.pdf"
    return StreamingResponse(BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename=\"{filename}\"'}
    )
