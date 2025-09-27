from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, PlainTextResponse
from pathlib import Path
from io import BytesIO
from typing import Dict, Any, List, Literal

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app import storage

# NIENTE prefix qui: lo aggiungiamo in main.py
router = APIRouter(tags=["export"])

# -------- Font embedding per KDP (consigliato da Amazon) --------
_EMBED_FONT_NAME = "DejaVuSerif"
_EMBED_FONT_FILE = Path(__file__).parent.parent / "assets" / "fonts" / "DejaVuSerif.ttf"
_HAS_EMBED = False
try:
    if _EMBED_FONT_FILE.exists():
        pdfmetrics.registerFont(TTFont(_EMBED_FONT_NAME, str(_EMBED_FONT_FILE)))
        _HAS_EMBED = True
except Exception:
    _HAS_EMBED = False


# ---------------- Helpers ----------------
def _read_book(book_id: str) -> Dict[str, Any]:
    book_dir = storage.BOOKS_DIR / book_id
    meta = book_dir / "book.json"
    if not meta.exists():
        raise HTTPException(status_code=404, detail="Libro non trovato")
    data = storage.read_json(meta)
    chapters: List[Dict[str, Any]] = data.get("chapters") or []
    if not chapters:
        ch_dir = storage.CHAPTERS_DIR / book_id
        if ch_dir.exists():
            for p in sorted(ch_dir.glob("*.txt")):
                chapters.append({"title": p.stem, "content": p.read_text(encoding="utf-8")})
    data["chapters"] = chapters
    return data


def _wrap_lines(cpl: int, text: str):
    from textwrap import wrap
    for line in text.splitlines():
        if not line.strip():
            yield ""
        else:
            for chunk in wrap(line, cpl):
                yield chunk


# ---------------- PDF normale (A4) ----------------
def _pdf_normal(book: Dict[str, Any]) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(book.get("title") or "Documento")

    font = _EMBED_FONT_NAME if _HAS_EMBED else "Helvetica"
    font_b = _EMBED_FONT_NAME if _HAS_EMBED else "Helvetica-Bold"

    width, height = A4
    margin = 25 * mm
    text_w = width - margin * 2
    y = height - margin

    c.setFont(font_b, 16)
    c.drawString(margin, y, book.get("title") or "Senza titolo")
    y -= 20
    c.setFont(font, 11)
    if book.get("author"):
        c.drawString(margin, y, f"Autore: {book['author']}")
        y -= 16
    y -= 6
    c.line(margin, y, margin + text_w, y)
    y -= 22

    leading = 16
    c.setFont(font, 12)
    for i, ch in enumerate(book["chapters"], start=1):
        title = ch.get("title") or f"Capitolo {i}"
        content = (ch.get("content") or "").strip()

        if y < 80 * mm:
            c.showPage(); c.setFont(font, 12); y = height - margin

        c.setFont(font_b, 13)
        c.drawString(margin, y, title)
        y -= 18
        c.setFont(font, 12)

        cpl = max(35, min(95, int(text_w / 6.2)))
        for chunk in _wrap_lines(cpl, content):
            if not chunk:
                y -= leading
            else:
                c.drawString(margin, y, chunk); y -= leading
            if y < 25 * mm:
                c.showPage(); c.setFont(font, 12); y = height - margin
        y -= 12

    c.showPage(); c.save()
    return buf.getvalue()


# ---------------- PDF KDP (A5 / 6x9) ----------------
def _page_size(trim: Literal["a5", "6x9"]):
    if (trim or "").lower() == "6x9":
        return (6 * inch, 9 * inch)
    return (148 * mm, 210 * mm)  # A5 default

def _pdf_kdp(book: Dict[str, Any], trim: Literal["a5", "6x9"]) -> bytes:
    page_w, page_h = _page_size(trim)
    gutter = 0.75 * inch
    outer  = 0.50 * inch
    top    = 0.50 * inch
    bottom = 0.50 * inch

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    c.setTitle(book.get("title") or "")
    c.setAuthor(book.get("author") or "")
    c.setSubject(f"Language: {book.get('language','it').upper()}")

    base = _EMBED_FONT_NAME if _HAS_EMBED else "Times-Roman"
    bold = _EMBED_FONT_NAME if _HAS_EMBED else "Times-Bold"
    c.setFont(base, 11.5)

    left = gutter
    text_w = page_w - left - outer
    y = page_h - top

    # front matter
    c.setFont(bold, 14)
    if book.get("title"):
        c.drawString(left, y, book["title"]); y -= 18
    c.setFont(base, 11.5)
    if book.get("author"):
        c.drawString(left, y, f"di {book['author']}"); y -= 16
    y -= 8; c.line(left, y, left + text_w, y); y -= 22

    page_num = 1
    def footer():
        nonlocal page_num
        c.setFont(base, 9)
        c.drawCentredString(page_w / 2, bottom - 0.2 * inch + 20, f"{page_num}")
        c.setFont(base, 11.5)
        page_num += 1

    leading = 15.5
    for i, ch in enumerate(book["chapters"], start=1):
        title = ch.get("title") or f"Capitolo {i}"
        content = (ch.get("content") or "").strip()

        if y < (bottom + 80):
            footer(); c.showPage(); c.setPageSize((page_w, page_h)); c.setFont(base, 11.5); y = page_h - top

        c.setFont(bold, 12.5)
        c.drawString(left, y, title); y -= 18
        c.setFont(base, 11.5)

        cpl = max(35, min(90, int(text_w / 5.8)))
        for chunk in _wrap_lines(cpl, content):
            if not chunk:
                y -= leading
            else:
                c.drawString(left, y, chunk); y -= leading
            if y < (bottom + 40):
                footer(); c.showPage(); c.setPageSize((page_w, page_h)); c.setFont(base, 11.5); y = page_h - top
        y -= 12

    footer(); c.showPage(); c.save()
    return buf.getvalue()


def _stream_pdf(bytes_: bytes, filename: str):
    return StreamingResponse(
        BytesIO(bytes_),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ---------------- ROUTES ----------------
@router.get("/books/{book_id}/export/pdf", summary="PDF normale o KDP (flag) — download")
def export_pdf(
    book_id: str,
    trim: str | None = Query(default=None, description='usa "6x9" per 6×9, altro=A5'),
    bleed: str | None = None,      # segnaposto per compatibilità UI
    classic: str | None = None,    # segnaposto per compatibilità UI
    cache_to_disk: bool = Query(default=False)
):
    """
    - Senza `cache_to_disk` => PDF normale A4 (download)
    - Con  `cache_to_disk=true` + `trim=a5|6x9` => PDF KDP conforme (download) e salvataggio su /static/books/<book_id>/exports/
    """
    book = _read_book(book_id)

    if cache_to_disk:
        size = "6x9" if (trim or "").lower() == "6x9" else "a5"
        pdf = _pdf_kdp(book, trim=size)

        # salva anche su disco per riuso/upload KDP
        out_dir = storage.BOOKS_DIR / book_id / "exports"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{book_id}_kdp_{size}.pdf"
        out_path.write_bytes(pdf)

        return _stream_pdf(pdf, out_path.name)

    # PDF normale (A4)
    pdf = _pdf_normal(book)
    return _stream_pdf(pdf, f"{book_id}.pdf")


@router.get("/books/{book_id}/export/md", summary="Markdown")
def export_md(book_id: str):
    book = _read_book(book_id)
    parts = [f"# {book.get('title','Senza titolo')}\n"]
    if book.get("author"):
        parts.append(f"*di {book['author']}*\n")
    for i, ch in enumerate(book["chapters"], start=1):
        parts.append(f"\n## {ch.get('title') or f'Capitolo {i}'}\n\n{ch.get('content') or ''}\n")
    return PlainTextResponse("".join(parts), media_type="text/markdown")


@router.get("/books/{book_id}/export/txt", summary="TXT")
def export_txt(book_id: str):
    book = _read_book(book_id)
    parts = [f"{book.get('title','Senza titolo')}\n"]
    if book.get("author"):
        parts.append(f"di {book['author']}\n")
    for i, ch in enumerate(book["chapters"], start=1):
        parts.append(f"\n=== {ch.get('title') or f'Capitolo {i}'} ===\n{ch.get('content') or ''}\n")
    return PlainTextResponse("".join(parts), media_type="text/plain; charset=utf-8")
    return (148 * mm, 210 * mm)  # A5 default


def _pdf_kdp(book: Dict[str, Any], trim: Literal["a5", "6x9"]) -> bytes:
    page_w, page_h = _page_size(trim)
    gutter = 0.75 * inch
    outer = 0.50 * inch
    top = 0.50 * inch
    bottom = 0.50 * inch

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    c.setTitle(book.get("title") or "")
    c.setAuthor(book.get("author") or "")
    c.setSubject(f"Language: {book.get('language','it').upper()}")

    base = _EMBED_FONT_NAME if _HAS_EMBED else "Times-Roman"
    bold = _EMBED_FONT_NAME if _HAS_EMBED else "Times-Bold"
    c.setFont(base, 11.5)

    left = gutter
    text_w = page_w - left - outer
    y = page_h - top

    c.setFont(bold, 14)
    if book.get("title"):
        c.drawString(left, y, book["title"])
        y -= 18
    c.setFont(base, 11.5)
    if book.get("author"):
        c.drawString(left, y, f"di {book['author']}")
        y -= 16
    y -= 8
    c.line(left, y, left + text_w, y)
    y -= 22

    page_num = 1

    def footer():
        nonlocal page_num
        c.setFont(base, 9)
        c.drawCentredString(page_w / 2, bottom - 0.2 * inch + 20, f"{page_num}")
        c.setFont(base, 11.5)
        page_num += 1

    leading = 15.5

    for i, ch in enumerate(book["chapters"], start=1):
        title = ch.get("title") or f"Capitolo {i}"
        content = (ch.get("content") or "").strip()

        if y < (bottom + 80):
            footer(); c.showPage(); c.setPageSize((page_w, page_h)); c.setFont(base, 11.5); y = page_h - top

        c.setFont(bold, 12.5)
        c.drawString(left, y, title)
        y -= 18
        c.setFont(base, 11.5)

        cpl = max(35, min(90, int(text_w / 5.8)))
        for chunk in _wrap_lines(cpl, content):
            if not chunk:
                y -= leading
            else:
                c.drawString(left, y, chunk); y -= leading
            if y < (bottom + 40):
                footer(); c.showPage(); c.setPageSize((page_w, page_h)); c.setFont(base, 11.5); y = page_h - top
        y -= 12

    footer()
    c.showPage()
    c.save()
    return buf.getvalue()


def _stream_pdf(bytes_: bytes, filename: str):
    return StreamingResponse(
        BytesIO(bytes_),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


def _md_text(book: Dict[str, Any]) -> str:
    parts = [f"# {book.get('title','Senza titolo')}\n"]
    if book.get("author"):
        parts.append(f"*di {book['author']}*\n")
    for i, ch in enumerate(book["chapters"], start=1):
        parts.append(f"\n## {ch.get('title') or f'Capitolo {i}'}\n\n{ch.get('content') or ''}\n")
    return "".join(parts)


def _txt_text(book: Dict[str, Any]) -> str:
    parts = [f"{book.get('title','Senza titolo')}\n"]
    if book.get("author"):
        parts.append(f"di {book['author']}\n")
    for i, ch in enumerate(book["chapters"], start=1):
        parts.append(f"\n=== {ch.get('title') or f'Capitolo {i}'} ===\n{ch.get('content') or ''}\n")
    return "".join(parts)


# --------- HANDLER PRINCIPALE (PDF/KDP) ----------
def _handle_pdf(book_id: str,
                trim: str | None,
                cache_to_disk: bool) -> StreamingResponse:
    book = _read_book(book_id)

    # KDP MODE: usiamo il TUO flag esistente cache_to_disk=true + trim (a5/6x9)
    kdp_mode = cache_to_disk is True
    filename = f"{book_id}.pdf"

    if kdp_mode:
        size = "6x9" if (trim or "").lower() == "6x9" else "a5"
        pdf = _pdf_kdp(book, trim=size)  # conforme KDP
        # salvataggio su /static (come facevi prima)
        out_dir = storage.BOOKS_DIR / book_id / "exports"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{book_id}_kdp_{size}.pdf"
        out_path.write_bytes(pdf)
        filename = out_path.name
        return _stream_pdf(pdf, filename)

    # PDF normale
    pdf = _pdf_normal(book)
    return _stream_pdf(pdf, filename)


# --------- ROUTES (compat legacy + api/v1) ----------
# LEGACY
@router.get("/export/books/{book_id}/export/pdf")
def export_pdf_legacy(
    book_id: str,
    trim: str | None = Query(default=None, description='usa "6x9" per 6×9, altro=A5'),
    bleed: str | None = None,
    classic: str | None = None,
    cache_to_disk: bool = Query(default=False)
):
    return _handle_pdf(book_id, trim, cache_to_disk)

@router.get("/export/books/{book_id}/export/md")
def export_md_legacy(book_id: str):
    book = _read_book(book_id)
    return PlainTextResponse(_md_text(book), media_type="text/markdown")

@router.get("/export/books/{book_id}/export/txt")
def export_txt_legacy(book_id: str):
    book = _read_book(book_id)
    return PlainTextResponse(_txt_text(book), media_type="text/plain; charset=utf-8")

# API V1 (stessi handler)
@router.get("/api/v1/export/books/{book_id}/export/pdf")
def export_pdf_v1(
    book_id: str,
    trim: str | None = Query(default=None),
    bleed: str | None = None,
    classic: str | None = None,
    cache_to_disk: bool = Query(default=False)
):
    return _handle_pdf(book_id, trim, cache_to_disk)

@router.get("/api/v1/export/books/{book_id}/export/md")
def export_md_v1(book_id: str):
    book = _read_book(book_id)
    return PlainTextResponse(_md_text(book), media_type="text/markdown")

@router.get("/api/v1/export/books/{book_id}/export/txt")
def export_txt_v1(book_id: str):
    book = _read_book(book_id)
    return PlainTextResponse(_txt_text(book), media_type="text/plain; charset=utf-8")
