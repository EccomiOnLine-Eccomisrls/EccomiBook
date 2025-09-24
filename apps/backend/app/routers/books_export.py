from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, PlainTextResponse
from typing import List, Dict, Tuple, Any
import io
from datetime import datetime
from pathlib import Path

# ReportLab
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, PageBreak
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch

# usa lo stesso storage del tuo progetto
from app import storage

router = APIRouter()

# ----------------- COSTANTI / UTILS -----------------
INCH = float(inch)
TRIMS = {
    "6x9":   (6*INCH, 9*INCH),
    "5x8":   (5*INCH, 8*INCH),
    "8.5x11":(8.5*INCH, 11*INCH),
}

def _kdp_gutter(pages: int) -> float:
    if pages <= 150: return 0.375*INCH
    if pages <= 300: return 0.50*INCH
    if pages <= 500: return 0.625*INCH
    return 0.75*INCH

def _register_ttf() -> Tuple[str,bool]:
    """Registra un TTF incorporabile se presente; fallback Helvetica."""
    candidates = [
        Path("/app/fonts/DejaVuSerif.ttf"),
        Path("./fonts/DejaVuSerif.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
    ]
    for p in candidates:
        try:
            if p.exists():
                pdfmetrics.registerFont(TTFont("BodySerif", str(p)))
                return "BodySerif", True
        except Exception:
            pass
    return "Helvetica", False

def _styles(font_name:str):
    base = getSampleStyleSheet()
    return {
        "H1": ParagraphStyle('H1', parent=base['Heading1'], fontName=font_name, fontSize=18, leading=22, spaceAfter=10),
        "H2": ParagraphStyle('H2', parent=base['Heading2'], fontName=font_name, fontSize=14, leading=18, spaceAfter=8),
        "Body": ParagraphStyle('Body', parent=base['BodyText'], fontName=font_name, fontSize=11, leading=15),
        "Italic": ParagraphStyle('Italic', parent=base['Italic'], fontName=font_name, fontSize=11, leading=15),
        "Small": ParagraphStyle('Small', parent=base['Normal'], fontName=font_name, fontSize=9, leading=12),
    }

def _make_story(book_title:str, author:str, chapters:List[Dict], styles) -> List:
    story=[]
    # Copertina
    story.append(Paragraph(book_title or "Senza titolo", styles["H1"]))
    if author:
        story.append(Paragraph(f"Autore: {author}", styles["Italic"]))
    story.append(Spacer(1, 16))
    story.append(Paragraph(
        f"Generato da EccomiBook — {datetime.utcnow():%d/%m/%Y %H:%M UTC}",
        styles["Small"]
    ))
    story.append(PageBreak())
    # Capitoli
    for i, ch in enumerate(chapters, 1):
        t = ch.get("title") or ch.get("id") or f"Capitolo {i:02d}"
        story.append(Paragraph(t, styles["H2"]))
        story.append(Spacer(1, 6))
        content = (ch.get("content") or "").strip() or "[Capitolo vuoto]"
        for para in content.split("\n\n"):
            story.append(Paragraph(para.replace("\n","<br/>"), styles["Body"]))
            story.append(Spacer(1, 6))
        if i < len(chapters):
            story.append(PageBreak())
    return story

def _build_pdf_mirror(page_size, margins, story):
    """Impaginazione a margini specchiati; ritorna (bytes, page_count)."""
    buf = io.BytesIO()
    doc = BaseDocTemplate(
        buf, pagesize=page_size,
        leftMargin=margins["left"], rightMargin=margins["right"],
        topMargin=margins["top"], bottomMargin=margins["bottom"],
        title="EccomiBook"
    )
    width, height = page_size

    frame_odd = Frame(
        x1=margins["left"], y1=margins["bottom"],
        width=width - margins["left"] - margins["right"],
        height=height - margins["top"] - margins["bottom"],
        id='frame_odd'
    )
    frame_even = Frame(
        x1=margins["right"], y1=margins["bottom"],
        width=width - margins["left"] - margins["right"],
        height=height - margins["top"] - margins["bottom"],
        id='frame_even'
    )

    def on_page(canvas, _doc):
        page = canvas.getPageNumber()
        canvas.setFont("Helvetica", 8)
        canvas.setFillGray(0.25)
        canvas.drawRightString(width - 36, 24, str(page))

    doc.addPageTemplates([
        PageTemplate(id='odd', frames=[frame_odd], onPage=on_page),
        PageTemplate(id='even', frames=[frame_even], onPage=on_page)
    ])
    doc.build(story)

    pdf_bytes = buf.getvalue()
    buf.close()
    # Conteggio robusto (PageBreak +1)
    page_count = max(1, sum(1 for x in story if isinstance(x, PageBreak)) + 1)
    return pdf_bytes, page_count

def _read_chapter_file(book_id:str, chapter_id:str) -> str:
    """Legge da <BASE_DIR>/chapters/{book_id}/{chapter_id}.md|txt"""
    base = storage.BASE_DIR / "chapters" / book_id
    for ext in (".md", ".txt"):
        p = (base / f"{chapter_id}{ext}")
        if p.exists():
            try:
                return p.read_text(encoding="utf-8")
            except Exception:
                return ""
    return ""

# ---------- NORMALIZZAZIONE DATI DALLO STORAGE ----------
def _load_books_meta() -> List[Dict[str, Any]]:
    """Ritorna sempre una lista di dict: [{'id':..., 'title':..., 'chapters':...}, ...]"""
    try:
        raw = storage.load_books_from_disk()
    except Exception:
        raw = []

    books: List[Dict[str, Any]] = []

    # Caso 1: già lista
    if isinstance(raw, list):
        for itm in raw:
            if isinstance(itm, dict):
                # ok
                books.append(itm)
            elif isinstance(itm, str):
                # solo id
                books.append({"id": itm, "title": itm, "chapters": []})

    # Caso 2: dict {id -> meta}
    elif isinstance(raw, dict):
        if "items" in raw and isinstance(raw["items"], list):
            for itm in raw["items"]:
                if isinstance(itm, dict):
                    books.append(itm)
        else:
            for bid, meta in raw.items():
                if isinstance(meta, dict):
                    b = {"id": bid, **meta}
                else:
                    b = {"id": bid, "title": str(meta), "chapters": []}
                books.append(b)

    # Fallback
    return books

def _norm_chapters_list(ch_list: Any) -> List[Dict[str, Any]]:
    """Ritorna lista di capitoli come dict con 'id' e opzionale 'title'."""
    out: List[Dict[str, Any]] = []
    if isinstance(ch_list, list):
        for c in ch_list:
            if isinstance(c, dict):
                cid = c.get("id") or c.get("chapter_id")
                if cid:
                    out.append({"id": cid, "title": c.get("title") or ""})
            elif isinstance(c, str):
                out.append({"id": c, "title": ""})
    return out

# ----------------- EXPORT CORE -----------------
def build_book_pdf_kdp(book_title:str, author:str, chapters:List[Dict],
                       trim:str="6x9", bleed:bool=False,
                       outer_margin_in:float=0.5, top_bottom_in:float=0.5) -> Tuple[bytes,int,bool]:
    page_w, page_h = TRIMS.get(trim, TRIMS["6x9"])
    bleed_add = (0.125*INCH if bleed else 0.0)
    page_size = (page_w + 2*bleed_add, page_h + 2*bleed_add)

    font_name, embedded = _register_ttf()
    styles = _styles(font_name)

    # Pre-story (stima pagine)
    prelim = _make_story(book_title, author, chapters, styles)
    prelim_margins = dict(
        left=(outer_margin_in*INCH)+bleed_add,
        right=(outer_margin_in*INCH)+bleed_add,
        top=(top_bottom_in*INCH)+bleed_add,
        bottom=(top_bottom_in*INCH)+bleed_add,
    )
    _, prelim_pages = _build_pdf_mirror(page_size, prelim_margins, prelim)
    prelim_pages = max(24, prelim_pages or 24)  # minimo editoriale

    gutter = _kdp_gutter(prelim_pages)
    final_margins = dict(
        left=(outer_margin_in*INCH + gutter)+bleed_add,
        right=(outer_margin_in*INCH)+bleed_add,
        top=prelim_margins["top"],
        bottom=prelim_margins["bottom"],
    )
    story = _make_story(book_title, author, chapters, styles)
    pdf_bytes, final_pages = _build_pdf_mirror(page_size, final_margins, story)
    return pdf_bytes, final_pages, embedded

# ----------------- ENDPOINTS -----------------
@router.get("/books/{book_id}/export/pdf", name="Export Book Pdf (KDP)")
async def export_book_pdf_kdp(book_id: str,
                              trim: str = "6x9",
                              bleed: bool = False,
                              outer_margin: float = 0.5,
                              top_bottom_margin: float = 0.5,
                              classic: bool = False):
    # ricarica sempre da disco e normalizza
    all_books = _load_books_meta()
    meta = next((b for b in all_books if (b.get("id") or b.get("book_id")) == book_id), None)
    if not meta:
        raise HTTPException(status_code=404, detail="Libro non trovato.")

    ch_meta = _norm_chapters_list(meta.get("chapters") or [])
    if not ch_meta:
        raise HTTPException(status_code=404, detail="Nessun capitolo nel libro.")

    # carica contenuti
    chapters_full = []
    for ch in ch_meta:
        cid = ch["id"]
        text = _read_chapter_file(book_id, cid)
        if not text and hasattr(storage, "read_chapter_text"):
            try:
                text = storage.read_chapter_text(book_id, cid) or ""
            except Exception:
                text = ""
        chapters_full.append({"id": cid, "title": ch.get("title") or cid, "content": text})

    if not chapters_full:
        raise HTTPException(status_code=404, detail="Impossibile assemblare i capitoli.")

    if classic:
        font_name, embedded = _register_ttf()
        styles = _styles(font_name)
        buffer = io.BytesIO()
        doc = BaseDocTemplate(buffer, pagesize=A4,
                              leftMargin=2*inch, rightMargin=2*inch,
                              topMargin=2*inch, bottomMargin=2*inch,
                              title=meta.get("title") or "EccomiBook")
        frame = Frame(2*inch, 2*inch, A4[0]-4*inch, A4[1]-4*inch)
        doc.addPageTemplates([PageTemplate(id='a4', frames=[frame])])
        doc.build(_make_story(meta.get("title") or book_id, meta.get("author") or "", chapters_full, styles))
        pdf_bytes = buffer.getvalue(); buffer.close()
        # stima pagine
        pages = max(1, sum(1 for x in _make_story(meta.get("title") or book_id, meta.get("author") or "", chapters_full, styles) if isinstance(x, PageBreak)) + 1)
        embedded_flag = embedded
    else:
        pdf_bytes, pages, embedded_flag = build_book_pdf_kdp(
            book_title = meta.get("title") or book_id,
            author     = meta.get("author") or "",
            chapters   = chapters_full,
            trim       = trim,
            bleed      = bleed,
            outer_margin_in    = outer_margin if outer_margin is not None else 0.5,
            top_bottom_in      = top_bottom_margin if top_bottom_margin is not None else 0.5
        )

    filename = f"{(meta.get('title') or book_id).replace(' ','_')}.pdf"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-KDP-Pages": str(pages),
        "X-Fonts-Embedded": "yes" if (not classic and embedded_flag) else "no"
    }
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)

@router.get("/books/{book_id}/export/md", response_class=PlainTextResponse, name="Export Book Md")
@router.get("/books/{book_id}/export/txt", response_class=PlainTextResponse, name="Export Book Txt")
async def export_book_text(book_id: str):
    all_books = _load_books_meta()
    meta = next((b for b in all_books if (b.get("id") or b.get("book_id")) == book_id), None)
    if not meta:
        raise HTTPException(status_code=404, detail="Libro non trovato.")

    ch_meta = _norm_chapters_list(meta.get("chapters") or [])
    if not ch_meta:
        raise HTTPException(status_code=404, detail="Nessun capitolo nel libro.")

    chunks = [f"# {meta.get('title') or book_id}\n\nAutore: {meta.get('author') or '—'}\n"]
    for ch in ch_meta:
        cid = ch["id"];  t = (ch.get("title") or cid)
        txt = _read_chapter_file(book_id, cid)
        if not txt and hasattr(storage, "read_chapter_text"):
            try:
                txt = storage.read_chapter_text(book_id, cid) or ""
            except Exception:
                txt = ""
        chunks.append(f"\n\n# {t}\n\n{txt}")
    body = "".join(chunks)
    return PlainTextResponse(body, media_type="text/markdown; charset=utf-8")
