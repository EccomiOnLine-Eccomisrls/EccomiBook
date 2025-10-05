# apps/backend/app/routers/books_export.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, PlainTextResponse
from typing import List, Tuple
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from pathlib import Path
from datetime import datetime

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app import storage

router = APIRouter()

# =========================================================
# Font & pagina
# =========================================================

# Prova a registrare font Unicode comuni; fallback a Helvetica
_BODY_FONT = "Helvetica"
_BODY_FONT_BOLD = "Helvetica-Bold"
_FONTS_TRIED = False

def _ensure_fonts():
    """Registra un font Unicode se disponibile (DejaVu / Noto)."""
    global _FONTS_TRIED, _BODY_FONT, _BODY_FONT_BOLD
    if _FONTS_TRIED:
        return
    _FONTS_TRIED = True

    candidates = [
        # (Regular, Bold)
        ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
        ("/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf",
         "/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    # anche path locali del progetto (opzionali)
    base_local = Path(__file__).resolve().parents[3]  # apps/backend/
    local_candidates = [
        (base_local / "assets" / "fonts" / "DejaVuSerif.ttf",
         base_local / "assets" / "fonts" / "DejaVuSerif-Bold.ttf"),
        (base_local / "assets" / "fonts" / "NotoSerif-Regular.ttf",
         base_local / "assets" / "fonts" / "NotoSerif-Bold.ttf"),
    ]
    for reg, bold in candidates + local_candidates:
        try:
            if Path(reg).exists() and Path(bold).exists():
                pdfmetrics.registerFont(TTFont("BookBody", str(reg)))
                pdfmetrics.registerFont(TTFont("BookBody-Bold", str(bold)))
                _BODY_FONT = "BookBody"
                _BODY_FONT_BOLD = "BookBody-Bold"
                break
        except Exception:
            # se fallisce, si resta su Helvetica
            pass

def _resolve_pagesize(kind: str):
    k = (kind or "").strip().lower()
    if k in ("6x9", "6×9", "6in x 9in"):
        return (6 * inch, 9 * inch)
    if k in ("5x8", "5×8", "5in x 8in"):
        return (5 * inch, 8 * inch)
    # default: A4
    return A4

# =========================================================
# Helpers di dominio
# =========================================================

def _get_book_or_404(book_id: str) -> dict:
    b = storage.find_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    return b

def _chapter_body(book: dict, ch: dict) -> str:
    # 1) inline (più aggiornato)
    txt = (ch.get("content") or ch.get("text") or "").strip()
    if txt:
        return txt

    # 2) content_path (fallback su disco)
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

    # 3) convenzione /chapters/<book>/<chapter>.txt
    bid = book.get("id") or book.get("book_id")
    cid = ch.get("id") or ch.get("chapter_id") or ch.get("cid")
    if bid and cid:
        p2 = storage.CHAPTERS_DIR / bid / f"{cid}.txt"
        if p2.exists():
            try:
                return p2.read_text(encoding="utf-8")
            except Exception:
                pass
    return ""

def _collect_book_texts(book: dict) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for ch in (book.get("chapters") or []):
        title = str(ch.get("title") or "Senza titolo")
        text = _chapter_body(book, ch)
        out.append((title, text))
    return out

# =========================================================
# Rendering PDF (KDP-ready)
# =========================================================

def _wrap_text(text: str, canv: canvas.Canvas, max_w: float, font_name: str, font_size: int) -> List[str]:
    out: List[str] = []
    for raw_line in (text or "").splitlines():
        words = raw_line.split(" ")
        line = ""
        for w in words:
            trial = (line + " " + w).strip()
            if canv.stringWidth(trial, font_name, font_size) <= max_w:
                line = trial
            else:
                if line:
                    out.append(line)
                line = w
        out.append(line)
    return out

def _wrap_title(title: str, canv: canvas.Canvas, max_w: float, font_name: str, font_size: int) -> List[str]:
    return _wrap_text(title, canv, max_w, font_name, font_size)

def _draw_footer(c: canvas.Canvas, *, width: float, left: float, right: float, bottom: float,
                 footer_left: str, footer_right: str, font: str, font_size: int):
    # posiziona al centro del margine inferiore
    y = bottom / 2.0
    c.setFont(font, font_size)
    # sinistra: titolo/autore
    c.drawString(left, y, footer_left[:120])
    # destra: numero pagina
    pr_w = c.stringWidth(footer_right, font, font_size)
    c.drawString(width - right - pr_w, y, footer_right)
                     
# --- KDP helpers (nuovi) ---
def _kdp_margins_cm(has_bleed: bool = False) -> dict:
    """
    Margini "tipografici" (cm) per b/n senza bleed.
    Modifica qui se vuoi più aria.
    """
    return dict(
        top=2.0,       # cm
        bottom=2.0,    # cm
        inner=2.0,     # cm, lato dorso
        outer=1.5      # cm, lato esterno
    )

def _draw_header_footer(c: canvas.Canvas, width: float, height: float,
                        page_num: int, book_title: str, chapter_title: str,
                        font_name: str):
    # Pari = sinistra • Dispari = destra (fronte/retro)
    is_even = (page_num % 2 == 0)
    header_y = height - 1.2 * cm
    footer_y = 1.2 * cm

    c.setFont(font_name, 9)

    # Header: titolo libro lato esterno, titolo capitolo lato interno
    if is_even:
        # pagina pari -> esterno a sinistra
        c.drawString(1.5 * cm, header_y, (book_title or "")[:120])
        c.drawRightString(width - 1.5 * cm, header_y, (chapter_title or "")[:120])
        # numero pagina lato interno (destra su pari)
        c.drawRightString(width - 2.0 * cm, footer_y, str(page_num))
    else:
        # pagina dispari -> esterno a destra
        c.drawString(2.0 * cm, header_y, (chapter_title or "")[:120])
        c.drawRightString(width - 1.5 * cm, header_y, (book_title or "")[:120])
        # numero pagina lato interno (sinistra su dispari)
        c.drawString(2.0 * cm, footer_y, str(page_num))
        
def _render_pdf(
    book_title: str,
    author: str | None,
    items: List[Tuple[str, str]],
    *,
    show_cover: bool = True,
    page_size=A4,
    margins_cm: Tuple[float, float, float, float] = (2.0, 2.0, 2.0, 2.0),  # L, R, T, B (ignorati per KDP speculare)
    body_font_size: int = 11,
    line_h: int = 15,
) -> bytes:
    _ensure_fonts()

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=page_size)
    width, height = page_size

    # Margini KDP (cm)
    km = _kdp_margins_cm()

    # Utilities per calcolare frame speculare
    def frame_left_for(pn: int) -> float:
        # pari: interno a sinistra; dispari: interno a destra
        return (km["inner"] * cm) if (pn % 2 == 0) else (km["outer"] * cm)

    def frame_right_for(pn: int) -> float:
        # pari: esterno a destra; dispari: esterno a sinistra
        return width - ((km["outer"] * cm) if (pn % 2 == 0) else (km["inner"] * cm))

    top_margin = km["top"] * cm
    bottom_margin = km["bottom"] * cm

    # Metadati PDF
    c.setTitle(book_title or "EccomiBook")

    # Cover interna semplice (senza header/footer)
    if show_cover:
        c.setFont(_BODY_FONT_BOLD, 22)
        c.drawCentredString(width / 2.0, height - 6 * cm, (book_title or ""))
        if author:
            c.setFont(_BODY_FONT, 14)
            c.drawCentredString(width / 2.0, height - 7 * cm, f"di {author}")
        c.setFont(_BODY_FONT, 10)
        c.drawCentredString(
            width / 2.0, 2 * cm,
            f"Generato con EccomiBook — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        )
        c.showPage()

    page_num = 1  # prima pagina di contenuto
    c.setFont(_BODY_FONT, body_font_size)

    for chapter_title, chapter_text in items:
        # Ogni capitolo su pagina DISPARI (1,3,5…) per prassi editoriale
        if page_num > 1 and page_num % 2 == 0:
            c.showPage()
            page_num += 1

        # Header/footer pagina corrente
        _draw_header_footer(c, width, height, page_num, (book_title or ""), (chapter_title or ""), _BODY_FONT)

        left = frame_left_for(page_num)
        right = frame_right_for(page_num)
        usable_w = right - left
        y = height - top_margin

        # Titolo capitolo (bandiera sinistra)
        c.setFont(_BODY_FONT_BOLD, 16)
        for tl in _wrap_text((chapter_title or "Senza titolo"), c, usable_w, _BODY_FONT_BOLD, 16):
            if y < bottom_margin + line_h:
                c.showPage()
                page_num += 1
                _draw_header_footer(c, width, height, page_num, (book_title or ""), (chapter_title or ""), _BODY_FONT)
                left = frame_left_for(page_num)
                right = frame_right_for(page_num)
                usable_w = right - left
                y = height - top_margin
            c.drawString(left, y, tl)
            y -= (line_h + 2)

        y -= (line_h // 2)
        c.setFont(_BODY_FONT, body_font_size)

        # Corpo del capitolo
        for line in _wrap_text((chapter_text or ""), c, usable_w, _BODY_FONT, body_font_size):
            if y < bottom_margin + line_h:
                c.showPage()
                page_num += 1
                _draw_header_footer(c, width, height, page_num, (book_title or ""), (chapter_title or ""), _BODY_FONT)
                left = frame_left_for(page_num)
                right = frame_right_for(page_num)
                usable_w = right - left
                y = height - top_margin
                c.setFont(_BODY_FONT, body_font_size)
            c.drawString(left, y, line)
            y -= line_h

        # Pagina successiva (separatore capitolo)
        c.showPage()
        page_num += 1

    c.save()
    buf.seek(0)
    return buf.read()

# =========================================================
# Endpoints
# =========================================================

@router.get("/export/books/{book_id}/export/pdf")
def export_book_pdf(
    book_id: str,
    cover: bool = Query(True, description="Includi pagina di copertina"),
    size: str = Query("A4", description="A4 | 6x9 | 5x8"),
):
    book = _get_book_or_404(book_id)
    items = _collect_book_texts(book)
    pdf_bytes = _render_pdf(
        book.get("title") or "Senza titolo",
        book.get("author"),
        items,
        show_cover=cover,
        page_size=_resolve_pagesize(size),
    )
    filename = f"{book.get('id','book')}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
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

# ✅ GET/POST compat (legacy)
@router.api_route("/export/books/{book_id}/export/kdp", methods=["GET", "POST"])
def export_book_kdp(
    book_id: str,
    size: str = Query("A4", description="A4 | 6x9 | 5x8"),
):
    """
    Restituisce un .zip con:
      - interior.pdf (senza cover, pronto KDP)
      - metadata.txt
    """
    book = _get_book_or_404(book_id)
    items = _collect_book_texts(book)
    pdf_bytes = _render_pdf(
        book.get("title") or "Senza titolo",
        book.get("author"),
        items,
        show_cover=False,  # Interior KDP: niente cover
        page_size=_resolve_pagesize(size),
    )

    zip_buf = BytesIO()
    with ZipFile(zip_buf, "w", ZIP_DEFLATED) as z:
        z.writestr("interior.pdf", pdf_bytes)
        meta = [
            f"Title: {book.get('title') or 'Senza titolo'}",
            f"Author: {book.get('author') or ''}",
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            f"Chapters: {len(items)}",
            f"Trim size: {size}",
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
def export_single_chapter_pdf(
    book_id: str,
    chapter_id: str,
    cover: bool = Query(False, description="Cover pagina iniziale (default: False)"),
    size: str = Query("A4", description="A4 | 6x9 | 5x8"),
):
    book = _get_book_or_404(book_id)
    ch = next((c for c in (book.get("chapters") or [])
               if str(c.get("id") or c.get("chapter_id") or c.get("cid")) == str(chapter_id)), None)
    if not ch:
        raise HTTPException(status_code=404, detail="Capitolo non trovato")

    title = str(ch.get("title") or "Senza titolo")
    body  = _chapter_body(book, ch)
    pdf_bytes = _render_pdf(
        f"{book.get('title') or 'Libro'} — {title}",
        book.get("author"),
        [(title, body)],
        show_cover=cover,  # anteprima capitolo di default SENZA cover
        page_size=_resolve_pagesize(size),
    )
    filename = f"{book.get('id','book')}_{chapter_id}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )

# -------- Preview capitolo via POST (testo volatile) --------
from pydantic import BaseModel

class ChapterPreviewIn(BaseModel):
    book_title: str | None = None
    author: str | None = None
    chapter_title: str
    text: str

@router.post("/export/preview/chapter/pdf")
def export_preview_chapter_pdf(
    body: ChapterPreviewIn,
    size: str = Query("A4", description="A4 | 6x9 | 5x8"),
):
    items = [(body.chapter_title or "Senza titolo", body.text or "")]
    pdf_bytes = _render_pdf(
        body.book_title or "Bozza libro",
        body.author,
        items,
        show_cover=False,
        page_size=_resolve_pagesize(size),
    )
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="preview_chapter.pdf"'}
    )
