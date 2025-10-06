# apps/backend/app/routers/books_export.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, PlainTextResponse, FileResponse
from typing import List, Tuple
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import re

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
    if k in ("6x9", "6×9", "6in x 9in", "kdp"):
        return (6 * inch, 9 * inch)
    if k in ("5x8", "5×8", "5in x 8in"):
        return (5 * inch, 8 * inch)
    return A4  # default

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

def _draw_typographic_cover(c: canvas.Canvas, *, width, height, title, author, theme="auto"):
    # Semplice cover tipografica “pulita”: titolo centrato, autore sotto
    # Piccolo accento cromatico se vuoi (qui usiamo solo nero per semplicità KDP safe)
    top_y = height * 0.62
    c.setFont(_BODY_FONT_BOLD, 28)
    for i, line in enumerate(_wrap_title(title or "", c, width*0.8, _BODY_FONT_BOLD, 28)):
        c.drawCentredString(width/2.0, top_y - i*34, line)
    if author:
        c.setFont(_BODY_FONT, 14)
        c.drawCentredString(width/2.0, top_y - 34*len(_wrap_title(title or "", c, width*0.8, _BODY_FONT_BOLD, 28)) - 18, f"di {author}")

    c.setFont(_BODY_FONT, 9)
    c.drawCentredString(width/2.0, 1.8*cm, "Creato con EccomiBook")

def _draw_typographic_backcover(c: canvas.Canvas, *, width, height, text=None):
    # Quarta di copertina minimal (testo giustificato semplice a bandiera)
    c.setFont(_BODY_FONT_BOLD, 16)
    c.drawString(2*cm, height - 3*cm, "Quarta di copertina")
    c.setFont(_BODY_FONT, 11)
    max_w = width - 4*cm
    y = height - 4.2*cm
    body = (text or "Questo libro è stato realizzato con EccomiBook. "
                    "Descrivi qui la sinossi, i benefici per il lettore, il target e l’autore.")
    for line in _wrap_text(body, c, max_w, _BODY_FONT, 11):
        if y < 2*cm + 11:
            break
        c.drawString(2*cm, y, line)
        y -= 15
        
def _render_pdf(
    book_title: str,
    author: str | None,
    items: List[Tuple[str, str]],
    *,
    show_cover: bool = True,            # retro-compat (se True equivale a cover_mode="front")
    cover_mode: str = "none",           # "none" | "front" | "front_back"
    backcover_text: str | None = None,  # testo opzionale quarta
    page_size=A4,
    margins_cm: Tuple[float, float, float, float] = (2.0, 2.0, 2.0, 2.0),  # L,R,T,B
    body_font_size: int = 11,
    line_h: int = 15,
) -> bytes:
    _ensure_fonts()

    # Normalizza cover_mode per compat
    if show_cover and cover_mode == "none":
        cover_mode = "front"

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=page_size)
    width, height = page_size

    ml, mr, mt, mb = [v * cm for v in margins_cm]
    max_width = width - ml - mr

    c.setTitle(book_title or "EccomiBook")

    page_num = 0

    # ------ COVER FRONT ------
    if cover_mode in ("front", "front_back"):
        _draw_typographic_cover(
            c, width=width, height=height,
            title=(book_title or ""), author=author, theme="auto"
        )
        c.showPage()  # la cover non ha footer/intestazioni

    # ------ CONTENUTO ------
    footer_left = f"{book_title or ''}" + (f" — {author}" if author else "")
    y = height - mt
    c.setFont(_BODY_FONT, body_font_size)

    def draw_footer_if_needed():
        if items:
            page_str = str(page_num if page_num >= 1 or cover_mode == "none" else 1)
            _draw_footer(
                c,
                width=width, left=ml, right=mr, bottom=mb,
                footer_left=footer_left,
                footer_right=page_str,
                font=_BODY_FONT, font_size=9
            )

    for idx, (title, text) in enumerate(items, start=1):
        if y < mb + (line_h * 3):
            draw_footer_if_needed()
            c.showPage()
            page_num += 1
            y = height - mt
            c.setFont(_BODY_FONT, body_font_size)

        # intestazione semplice (titolo capitolo)
        title_lines = _wrap_title(title or "Senza titolo", c, max_width, _BODY_FONT_BOLD, 16)
        c.setFont(_BODY_FONT_BOLD, 16)
        for tl in title_lines:
            c.drawCentredString(width / 2.0, y, tl)
            y -= (line_h + 2)
        y -= (line_h // 2)
        c.setFont(_BODY_FONT, body_font_size)

        para_lines = _wrap_text(text or "", c, max_width, _BODY_FONT, body_font_size)
        for line in para_lines:
            if y < mb + line_h:
                draw_footer_if_needed()
                c.showPage()
                page_num += 1
                y = height - mt
                c.setFont(_BODY_FONT, body_font_size)
            c.drawString(ml, y, line)
            y -= line_h

        y -= (line_h * 2)

    if items:
        draw_footer_if_needed()

    # ------ BACK COVER (quarta) ------
    if cover_mode == "front_back":
        c.showPage()
        _draw_typographic_backcover(c, width=width, height=height, text=backcover_text)

    c.save()
    buf.seek(0)
    return buf.read()

# =========================================================
# AI-like Cover (placeholder locale, no AI)
# =========================================================

_COVER_DIR = Path("/tmp/eccomibook_covers")
_COVER_DIR.mkdir(parents=True, exist_ok=True)

def _slugify(x: str) -> str:
    x = re.sub(r"\s+", "-", x.strip())
    x = re.sub(r"[^a-zA-Z0-9\-_.]", "", x)
    return x.lower()[:80] or "cover"

def _pick_colors(style: str) -> tuple[str, str]:
    s = (style or "").lower()
    if "artist" in s:   return ("#1f2937", "#f59e0b")  # dark + amber
    if "photo" in s:    return ("#0f172a", "#e2e8f0")  # very dark + light
    if "light" in s:    return ("#ffffff", "#111827")  # white + near-black
    if "dark" in s:     return ("#0b0f19", "#e5e7eb")  # dark + light gray
    return ("#fafafa", "#111827")                      # default tipografica

def _load_font(size: int, bold=False) -> ImageFont.FreeTypeFont:
    # Prova font comuni; fallback a font di default
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"  if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf"     if bold else "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf",
    ]
    for p in candidates:
        try:
            if Path(p).exists():
                return ImageFont.truetype(p, size=size)
        except Exception:
            pass
    return ImageFont.load_default()

def _wrap_text_pil(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in (text or "").split():
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur: lines.append(cur)
            cur = word
    if cur: lines.append(cur)
    # preserva ritorni a capo manuali
    out = []
    for line in "\n".join(lines).splitlines():
        out.append(line)
    return out

def create_cover_image(title: str, author: str = "", style: str = "tipografica", size: str = "6x9") -> str:
    # Misure “fronte” a 300 DPI (KDP: 6x9 -> 1800x2700). A4: 2480x3508
    if (size or "").lower() in ("6x9", "kdp"):
        W, H = 1800, 2700
    elif (size or "").lower() in ("5x8",):
        W, H = 1500, 2400
    else:  # A4
        W, H = 2480, 3508

    bg, fg = _pick_colors(style)
    im = Image.new("RGB", (W, H), bg)
    d  = ImageDraw.Draw(im)

    # Cornice leggera
    d.rectangle([40, 40, W-40, H-40], outline=fg, width=4)

    # Tipografia
    f_title = _load_font(96, bold=True)
    f_sub   = _load_font(48, bold=False)

    # Box di impaginazione
    pad = 140
    max_w = W - pad*2

    # Titolo (centrato)
    title = (title or "").strip() or "Senza titolo"
    t_lines = _wrap_text_pil(d, title, f_title, max_w)
    y = int(H*0.25)
    for line in t_lines:
        tw = d.textlength(line, font=f_title)
        d.text(((W-tw)//2, y), line, font=f_title, fill=fg)
        y += int(f_title.size * 1.15)

    # Autore (sotto titolo)
    if author:
        a = f"di {author}"
        aw = d.textlength(a, font=f_sub)
        d.text(((W-aw)//2, y+20), a, font=f_sub, fill=fg)

    # Bollino discreto
    tag = "Creato con EccomiBook"
    d.text((W//2 - d.textlength(tag, font=_load_font(28))/2, H - 120), tag, font=_load_font(28), fill=fg)

    # Salva su /tmp ed esponi path
    fname = f"{_slugify(title)}_{_slugify(author)}_{_slugify(style)}_{W}x{H}.jpg"
    out_path = _COVER_DIR / fname
    im.save(out_path, format="JPEG", quality=92, optimize=True)
    return str(out_path)

# ============================================================
#  AI-like Cover Generator (local)
# ============================================================

from fastapi.responses import FileResponse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io

@router.get("/generate/cover")
async def generate_cover(
    title: str,
    author: str,
    style: str = "dark",
    size: str = "6x9"
):
    """Genera una copertina tipografica base (placeholder locale)"""
    width, height = (1800, 2700) if size == "6x9" else (2480, 3508)
    bg_color = "#111" if style == "dark" else "#fff"
    text_color = "#fff" if style == "dark" else "#000"

    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Titolo
    font_title = ImageFont.load_default()
    draw.text((width/2, height/2 - 50), title, fill=text_color, font=font_title, anchor="mm")

    # Autore
    draw.text((width/2, height/2 + 60), f"di {author}", fill=text_color, font=font_title, anchor="mm")

    # Salva in memoria e restituisci
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/jpeg")
    
# =========================================================
# Endpoints
# =========================================================

@router.get("/export/books/{book_id}/export/pdf")
def export_book_pdf(
    book_id: str,
    cover: bool = Query(True, description="(Compat) Includi copertina tipografica"),
    cover_mode: str = Query("front", description='"none" | "front" | "front_back"'),
    backcover_text: str | None = Query(None, description="Testo per la quarta di copertina"),
    size: str = Query("A4", description="A4 | 6x9 | 5x8"),
):
    book = _get_book_or_404(book_id)
    items = _collect_book_texts(book)
    pdf_bytes = _render_pdf(
        book.get("title") or "Senza titolo",
        book.get("author"),
        items,
        show_cover=cover,
        cover_mode=cover_mode,
        backcover_text=backcover_text,
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
    cover_mode: str = Query("none", description="none | front | front_back"),
    backcover_text: str | None = Query(None, description="Testo quarta di copertina"),
    ai_cover: bool = Query(False, description="Se true, genera copertina tipografica"),
    theme: str = Query("auto", description="auto | light | dark | color1 ..."),
):
    """
    Restituisce un .zip con:
      - interior.pdf (senza cover, pronto KDP)
      - (opz) cover_front.pdf
      - (opz) cover_back.pdf
      - metadata.txt
    """
    book = _get_book_or_404(book_id)
    items = _collect_book_texts(book)

    # --- Interior (sempre senza cover pagina interna) ---
    interior_bytes = _render_pdf(
        book.get("title") or "Senza titolo",
        book.get("author"),
        items,
        show_cover=False,
        page_size=_resolve_pagesize(size),
    )

    # --- Copertine opzionali ---
    cover_front = None
    cover_back  = None
    if cover_mode in ("front", "front_back") and ai_cover:
        # usa le cover tipografiche integrate
        buf_f = BytesIO()
        c = canvas.Canvas(buf_f, pagesize=_resolve_pagesize(size))
        _draw_typographic_cover(
            c, *c._pagesize, title=(book.get("title") or ""), author=book.get("author"), theme=theme
        )
        c.showPage(); c.save()
        buf_f.seek(0); cover_front = buf_f.read()

        if cover_mode == "front_back":
            buf_b = BytesIO()
            c2 = canvas.Canvas(buf_b, pagesize=_resolve_pagesize(size))
            _draw_typographic_backcover(c2, *c2._pagesize, text=backcover_text)
            c2.showPage(); c2.save()
            buf_b.seek(0); cover_back = buf_b.read()

    # --- ZIP out ---
    zip_buf = BytesIO()
    with ZipFile(zip_buf, "w", ZIP_DEFLATED) as z:
        z.writestr("interior.pdf", interior_bytes)
        if cover_front: z.writestr("cover_front.pdf", cover_front)
        if cover_back:  z.writestr("cover_back.pdf",  cover_back)
        meta = [
            f"Title: {book.get('title') or 'Senza titolo'}",
            f"Author: {book.get('author') or ''}",
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            f"Chapters: {len(items)}",
            f"Trim size: {size}",
            f"Cover mode: {cover_mode}",
            f"AI cover: {ai_cover}",
            f"Theme: {theme}",
            f"Backcover chars: {len(backcover_text or '')}",
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

@router.get("/generate/cover")
def generate_cover(
    title: str,
    author: str = "",
    style: str = "tipografica",
    size: str = "6x9"
):
    """
    Genera una copertina JPG (placeholder tipografico) per anteprime o mock KDP.
    style: tipografica | artistica | fotografica | light | dark
    size : 6x9 | 5x8 | A4
    """
    img_path = create_cover_image(title=title, author=author, style=style, size=size)
    filename = Path(img_path).name
    return FileResponse(img_path, media_type="image/jpeg", filename=filename)
