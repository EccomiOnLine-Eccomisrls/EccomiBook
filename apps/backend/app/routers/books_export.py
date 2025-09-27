from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pathlib import Path
from typing import Literal, List, Dict, Any
from io import BytesIO

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app import storage

router = APIRouter(
    prefix="/api/v1/export",
    tags=["export"]
)

# ---------- Font embedding (KDP raccomandato) ----------
# Se il TTF è presente lo embeddiamo; se manca, fallback a Helvetica.
_EMBEDDED_FONT_NAME = "DejaVuSerif"
_EMBEDDED_FONT_FILE = Path(__file__).parent.parent / "assets" / "fonts" / "DejaVuSerif.ttf"
_HAS_EMBED_FONT = False
try:
    if _EMBEDDED_FONT_FILE.exists():
        pdfmetrics.registerFont(TTFont(_EMBEDDED_FONT_NAME, str(_EMBEDDED_FONT_FILE)))
        _HAS_EMBED_FONT = True
except Exception:
    _HAS_EMBED_FONT = False


# ---------- Utils ----------
def _read_book(book_id: str) -> Dict[str, Any]:
    """Carica il book.json + capitoli dallo storage."""
    book_dir = storage.BOOKS_DIR / book_id
    book_json = book_dir / "book.json"
    if not book_json.exists():
        raise HTTPException(status_code=404, detail=f"Libro {book_id} non trovato")

    data = storage.read_json(book_json)
    # Capitoli: se nel JSON non ci sono i testi, proviamo cartella chapters
    chapters: List[Dict[str, Any]] = data.get("chapters", [])
    if not chapters:
        ch_dir = storage.CHAPTERS_DIR / book_id
        if ch_dir.exists():
            for p in sorted(ch_dir.glob("*.txt")):
                chapters.append({"title": p.stem, "content": p.read_text(encoding="utf-8")})
    data["chapters"] = chapters
    return data


def _draw_paragraphs(c: canvas.Canvas, text: str, left: float, top: float, width: float, leading: float):
    """Stampa testo semplice, a capo su parole."""
    # Semplice word-wrap
    from textwrap import wrap
    # 1000/width ~ stima character-per-line, dipende dal font; empirico per testi semplici
    est_cpl = max(35, min(95, int(width / 6.2)))
    y = top
    for line in text.splitlines():
        if not line.strip():
            y -= leading
            continue
        for chunk in wrap(line, est_cpl):
            c.drawString(left, y, chunk)
            y -= leading
    return y


def _pdf_bytes_normal(book: Dict[str, Any]) -> bytes:
    """PDF normale (A4) — download diretto."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(book.get("title") or "Documento")

    # Font
    if _HAS_EMBED_FONT:
        c.setFont(_EMBEDDED_FONT_NAME, 12)
    else:
        c.setFont("Helvetica", 12)

    width, height = A4
    margin = 25 * mm
    text_w = width - margin * 2
    y = height - margin

    # Titolo / autore
    c.setFont((_EMBEDDED_FONT_NAME if _HAS_EMBED_FONT else "Helvetica-Bold"), 16)
    c.drawString(margin, y, (book.get("title") or "Senza titolo"))
    y -= 20
    c.setFont((_EMBEDDED_FONT_NAME if _HAS_EMBED_FONT else "Helvetica"), 11)
    author = book.get("author") or ""
    if author:
        c.drawString(margin, y, f"Autore: {author}")
        y -= 18
    y -= 6
    c.line(margin, y, margin + text_w, y)
    y -= 22

    # Capitoli
    leading = 16
    for i, ch in enumerate(book.get("chapters", []), start=1):
        title = ch.get("title") or f"Capitolo {i}"
        content = (ch.get("content") or "").strip()

        # Se non c'è spazio, nuova pagina
        if y < 80 * mm:
            c.showPage()
            if _HAS_EMBED_FONT:
                c.setFont(_EMBEDDED_FONT_NAME, 12)
            else:
                c.setFont("Helvetica", 12)
            y = height - margin

        # titolo capitolo
        c.setFont((_EMBEDDED_FONT_NAME if _HAS_EMBED_FONT else "Helvetica-Bold"), 13)
        c.drawString(margin, y, title)
        y -= 18
        c.setFont((_EMBEDDED_FONT_NAME if _HAS_EMBED_FONT else "Helvetica"), 12)
        y = _draw_paragraphs(c, content, margin, y, text_w, leading) - 14

    c.showPage()
    c.save()
    return buf.getvalue()


def _page_size_for_kdp(size: Literal["a5", "6x9"]):
    if size == "6x9":
        return (6 * inch, 9 * inch)
    # default A5
    return (148 * mm, 210 * mm)


def _pdf_bytes_kdp(book: Dict[str, Any], size: Literal["a5", "6x9"]) -> bytes:
    """PDF KDP — formato libro, margini/gutter, font embedded, metadata puliti."""
    page_w, page_h = _page_size_for_kdp(size)

    # Margini consigliati KDP (indicativi):
    # interno (gutter) 0.75", esterno 0.5", alto 0.5", basso 0.5"
    gutter = 0.75 * inch
    outer = 0.50 * inch
    top = 0.50 * inch
    bottom = 0.50 * inch

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    # Metadata
    c.setTitle(book.get("title") or "")
    c.setAuthor(book.get("author") or "")
    c.setSubject(f"Language: {book.get('language','it').upper()}")

    # Font (embed se disponibile)
    base_font = _EMBEDDED_FONT_NAME if _HAS_EMBED_FONT else "Times-Roman"
    bold_font = _EMBEDDED_FONT_NAME if _HAS_EMBED_FONT else "Times-Bold"
    c.setFont(base_font, 11.5)

    # area testo (pagina destra/sinistra: qui non alterniamo gutter per semplicità -> area centrale)
    left = gutter
    right_margin = outer
    text_w = page_w - left - right_margin
    y = page_h - top

    # front matter: titolo
    c.setFont(bold_font, 14)
    c.drawString(left, y, (book.get("title") or ""))
    y -= 18
    c.setFont(base_font, 11.5)
    if book.get("author"):
        c.drawString(left, y, f"di {book['author']}")
        y -= 16

    y -= 8
    c.line(left, y, left + text_w, y)
    y -= 22

    # numerazione pagine (richiesta spesso in corpo libro)
    page_num = 1

    def _footer():
        nonlocal page_num
        c.setFont(base_font, 9)
        c.drawCentredString(page_w / 2, bottom - 0.2 * inch + 20, f"{page_num}")
        c.setFont(base_font, 11.5)
        page_num += 1

    leading = 15.5

    # Capitoli
    for i, ch in enumerate(book.get("chapters", []), start=1):
        title = ch.get("title") or f"Capitolo {i}"
        content = (ch.get("content") or "").strip()

        # se poco spazio, pagina nuova
        if y < (bottom + 80):
            _footer()
            c.showPage()
            c.setPageSize((page_w, page_h))
            c.setFont(base_font, 11.5)
            y = page_h - top

        c.setFont(bold_font, 12.5)
        c.drawString(left, y, title)
        y -= 18
        c.setFont(base_font, 11.5)
        # wrap
        from textwrap import wrap
        est_cpl = max(35, min(90, int(text_w / 5.8)))
        for line in content.splitlines():
            if not line.strip():
                y -= leading
                continue
            for chunk in wrap(line, est_cpl):
                c.drawString(left, y, chunk)
                y -= leading
                if y < (bottom + 40):
                    _footer()
                    c.showPage()
                    c.setPageSize((page_w, page_h))
                    c.setFont(base_font, 11.5)
                    y = page_h - top

        y -= 12

    _footer()
    c.showPage()
    c.save()
    return buf.getvalue()


# ---------- ROUTES ----------

@router.get("/books/{book_id}/export/pdf", summary="PDF normale (A4) — download")
def export_pdf_stream(book_id: str):
    book = _read_book(book_id)
    pdf_bytes = _pdf_bytes_normal(book)
    filename = f"{book_id}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.post(
    "/books/{book_id}/export/kdp",
    summary="KDP PDF (A5 o 6x9) — salva su /static e restituisce URL"
)
def export_kdp_save(
    book_id: str,
    size: Literal["a5", "6x9"] = Query(default="a5", description="Formato pagina KDP")
):
    book = _read_book(book_id)
    pdf_bytes = _pdf_bytes_kdp(book, size=size)

    # Salvataggio su /static/books/<book_id>/exports/
    out_dir = storage.BOOKS_DIR / book_id / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = f"{book_id}_kdp_{size}.pdf"
    out_path = out_dir / out_name
    out_path.write_bytes(pdf_bytes)

    # URL pubblico (montato in app.main come StaticFiles su /static/books)
    # Se BOOKS_DIR è montata su /static/books, calcoliamo il relativo:
    rel = out_path.relative_to(storage.BOOKS_DIR)
    url = f"/static/books/{rel.as_posix()}"

    return JSONResponse({"status": "ok", "size": size, "path": str(rel), "url": url})
