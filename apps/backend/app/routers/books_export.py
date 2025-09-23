from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, PlainTextResponse
from typing import List, Dict, Tuple
import io
from datetime import datetime

# ReportLab
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, PageBreak
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

router = APIRouter()

# ========= TODO: COLLEGA QUESTI 3 HOOK AL TUO STORAGE =========
# Usa la stessa logica che alimenta:
# - GET /books
# - GET /books/{book_id}/chapters/{chapter_id}
async def _get_book_meta(book_id: str) -> Dict:
    """
    Ritorna {title, author, language?, chapters: [ {id, title, updated_at?}, ... ]} in ordine.
    """
    # TODO: sostituisci con la tua implementazione
    raise NotImplementedError

async def _list_chapters(book_id: str) -> List[Dict]:
    """
    Lista capitoli (ordinata). Minimo: [{id, title?}, ...]
    """
    # TODO: sostituisci con la tua implementazione
    raise NotImplementedError

async def _read_chapter_content(book_id: str, chapter_id: str) -> str:
    """
    Contenuto testuale del capitolo (come l'endpoint esistente).
    """
    # TODO: sostituisci con la tua implementazione
    raise NotImplementedError
# ===============================================================

INCH = 72.0
TRIMS = {
    "6x9":   (6*INCH, 9*INCH),
    "5x8":   (5*INCH, 8*INCH),
    "8.5x11":(8.5*INCH, 11*INCH),
}

def _kdp_gutter(points_count: int) -> float:
    """Gutter (pt) in base alle pagine (linee guida KDP)."""
    if points_count <= 150: return 0.375*INCH
    if points_count <= 300: return 0.50*INCH
    if points_count <= 500: return 0.625*INCH
    return 0.75*INCH

def _register_ttf(ttf_path:str, name:str="BodySerif") -> Tuple[str,bool]:
    """Registra TTF (embedded). Se fallisce, usa Helvetica (non embedded)."""
    try:
        pdfmetrics.registerFont(TTFont(name, ttf_path))
        return name, True
    except Exception:
        return "Helvetica", False

def _make_story(book_title:str, author:str, chapters:List[Dict],
                styles) -> List:
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

def _styles(font_name:str):
    base = getSampleStyleSheet()
    return {
        "H1": ParagraphStyle('H1', parent=base['Heading1'], fontName=font_name, fontSize=18, leading=22, spaceAfter=10),
        "H2": ParagraphStyle('H2', parent=base['Heading2'], fontName=font_name, fontSize=14, leading=18, spaceAfter=8),
        "Body": ParagraphStyle('Body', parent=base['BodyText'], fontName=font_name, fontSize=11, leading=15),
        "Italic": ParagraphStyle('Italic', parent=base['Italic'], fontName=font_name, fontSize=11, leading=15),
        "Small": ParagraphStyle('Small', parent=base['Normal'], fontName=font_name, fontSize=9, leading=12),
    }

def _build_pdf_mirrored(page_size, margins, story):
    """
    impagina con margini 'specchiati' (gutter interno).
    margins: dict {left, right, top, bottom}
    """
    buf = io.BytesIO()
    doc = BaseDocTemplate(
        buf, pagesize=page_size,
        leftMargin=margins["left"], rightMargin=margins["right"],
        topMargin=margins["top"], bottomMargin=margins["bottom"],
        title="EccomiBook"
    )

    width, height = page_size
    # Frames pari/dispari (gutter a sinistra per dispari, a destra per pari)
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

    def on_page(canvas, doc):
        # numerazione semplice (opzionale)
        page = canvas.getPageNumber()
        canvas.setFont("Helvetica", 8)
        canvas.setFillGray(0.25)
        canvas.drawRightString(width - 36, 24, str(page))

    doc.addPageTemplates([
        PageTemplate(id='odd', frames=[frame_odd], onPage=on_page),
        PageTemplate(id='even', frames=[frame_even], onPage=on_page)
    ])
    doc.build(story)
    return buf.getvalue(), doc.page  # bytes, page_count

def build_book_pdf_kdp(book_title:str, author:str, chapters:List[Dict],
                       trim:str="6x9", bleed:bool=False,
                       outer_margin_in:float=0.5, top_bottom_in:float=0.5,
                       font_path:str="/fonts/DejaVuSerif.ttf") -> Tuple[bytes,int,bool]:
    """
    Genera PDF con:
    - trim e bleed opzionali
    - font TTF embedded
    - gutter KDP e margini specchiati (left/right alternati)
    Ritorna: (pdf_bytes, page_count, fonts_embedded)
    """
    page_w, page_h = TRIMS.get(trim, TRIMS["6x9"])
    bleed_add = (0.125*INCH if bleed else 0.0)
    page_size = (page_w + 2*bleed_add, page_h + 2*bleed_add)

    font_name, embedded = _register_ttf(font_path)
    styles = _styles(font_name)

    # Pre-story per stimare pagine senza gutter
    prelim = _make_story(book_title, author, chapters, styles)
    prelim_margins = dict(
        left=(outer_margin_in*INCH)+bleed_add,
        right=(outer_margin_in*INCH)+bleed_add,
        top=(top_bottom_in*INCH)+bleed_add,
        bottom=(top_bottom_in*INCH)+bleed_add,
    )
    prelim_pdf, prelim_pages = _build_pdf_mirrored(page_size, prelim_margins, prelim)

    # Gutter in base alle pagine
    gutter = _kdp_gutter(prelim_pages)

    # Margini definitivi (gutter aggiunto al lato interno alternato -> specchiati)
    # Per ottenere il mirroring usiamo due Frame con x1 diversi (vedi _build_pdf_mirrored).
    final_margins = dict(
        left=(outer_margin_in*INCH + gutter)+bleed_add,
        right=(outer_margin_in*INCH)+bleed_add,
        top=prelim_margins["top"],
        bottom=prelim_margins["bottom"],
    )

    story = _make_story(book_title, author, chapters, styles)
    pdf_bytes, final_pages = _build_pdf_mirrored(page_size, final_margins, story)
    return pdf_bytes, final_pages, embedded


# ======================= ENDPOINTS =======================

@router.get("/books/{book_id}/export/pdf", name="Export Book Pdf (KDP)")
async def export_book_pdf_kdp(book_id: str,
                              trim: str = "6x9",
                              bleed: bool = False,
                              outer_margin: float = 0.5,
                              top_bottom_margin: float = 0.5,
                              classic: bool = False):
    """
    Esporta l'intero libro in PDF.
    - trim: 6x9 | 5x8 | 8.5x11
    - bleed: true/false
    - classic: true -> usa A4 e margini standard, senza gutter (PDF 'classico')
    """
    try:
        meta = await _get_book_meta(book_id)
        ch_list = await _list_chapters(book_id)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Storage hooks non implementati.")

    if not meta:
        raise HTTPException(status_code=404, detail="Libro non trovato.")
    if not ch_list:
        raise HTTPException(status_code=404, detail="Nessun capitolo nel libro.")

    chapters_full=[]
    for ch in ch_list:
        cid = ch.get("id")
        if not cid: 
            continue
        text = await _read_chapter_content(book_id, cid) or ""
        chapters_full.append({"id": cid, "title": ch.get("title") or cid, "content": text})

    if classic:
        # PDF “classico”: A4, margini 2cm, nessun gutter/bleed
        buffer = io.BytesIO()
        doc = BaseDocTemplate(buffer, pagesize=A4,
                              leftMargin=2*cm, rightMargin=2*cm,
                              topMargin=2*cm, bottomMargin=2*cm,
                              title=meta.get("title") or "EccomiBook")
        styles = _styles(_register_ttf("/fonts/DejaVuSerif.ttf")[0])
        frame = Frame(2*cm, 2*cm, A4[0]-4*cm, A4[1]-4*cm)
        doc.addPageTemplates([PageTemplate(id='a4', frames=[frame])])
        doc.build(_make_story(meta.get("title") or book_id, meta.get("author") or "", chapters_full, styles))
        pdf_bytes = buffer.getvalue(); buffer.close()
        pages = doc.page
        embedded = True
    else:
        pdf_bytes, pages, embedded = build_book_pdf_kdp(
            book_title = meta.get("title") or book_id,
            author     = meta.get("author") or "",
            chapters   = chapters_full,
            trim       = trim,
            bleed      = bleed,
            outer_margin_in    = outer_margin,
            top_bottom_in      = top_bottom_margin,
            font_path  = "/fonts/DejaVuSerif.ttf"   # <— aggiorna se metti un altro TTF
        )

    filename = f"{(meta.get('title') or book_id).replace(' ','_')}.pdf"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-KDP-Pages": str(pages),
        "X-Fonts-Embedded": "yes" if embedded else "no"
    }
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


@router.get("/books/{book_id}/export/md", response_class=PlainTextResponse, name="Export Book Md")
@router.get("/books/{book_id}/export/txt", response_class=PlainTextResponse, name="Export Book Txt")
async def export_book_text(book_id: str):
    try:
        meta = await _get_book_meta(book_id)
        ch_list = await _list_chapters(book_id)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Storage hooks non implementati.")

    if not meta:
        raise HTTPException(status_code=404, detail="Libro non trovato.")
    if not ch_list:
        raise HTTPException(status_code=404, detail="Nessun capitolo nel libro.")

    chunks = [f"# {meta.get('title') or book_id}\n\nAutore: {meta.get('author') or '—'}\n"]
    for ch in ch_list:
        cid = ch.get("id");  t = ch.get("title") or cid
        txt = await _read_chapter_content(book_id, cid) or ""
        chunks.append(f"\n\n# {t}\n\n{txt}")
    body = "".join(chunks)
    return PlainTextResponse(body, media_type="text/markdown; charset=utf-8")
