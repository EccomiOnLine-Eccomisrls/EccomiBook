from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse, PlainTextResponse
from typing import List, Dict, Tuple
import io
from datetime import datetime
from pathlib import Path
import hashlib

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

# storage condiviso
from app import storage

router = APIRouter()

# ----------------- COSTANTI & UTILS -----------------
INCH = 72.0
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
    """
    Prova a registrare un TTF incorporabile (embedded).
    Percorsi tentati (metti il file in uno di questi):
    - /app/fonts/DejaVuSerif.ttf
    - ./fonts/DejaVuSerif.ttf
    - /usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf
    """
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
    # fallback (non embedded, KDP può segnalare avviso)
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
    # Frontespizio minimal
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
    """
    Impaginazione con margini 'specchiati' (gutter interno alternato pari/dispari).
    margins: {left, right, top, bottom}
    """
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

    def on_page(canvas, doc):
        # footer con numero pagina (leggero)
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

def _read_chapter_file(book_id:str, chapter_id:str) -> str:
    """
    Legge il capitolo dalla cartella storage locale, provando .md poi .txt.
    Path: <BASE_DIR>/chapters/{book_id}/{chapter_id}.md|txt
    """
    base = storage.CHAPTERS_DIR / book_id
    for ext in (".md", ".txt"):
        p = (base / f"{chapter_id}{ext}")
        if p.exists():
            try:
                return p.read_text(encoding="utf-8")
            except Exception:
                return ""
    return ""

def _content_signature(chapters:List[Dict]) -> str:
    """
    Crea una firma contenuti basata su id + hash del testo (per invalidare cache se cambia).
    NB: per semplicità usiamo solo id+length; se vuoi, usa sha1(contents).
    """
    h = hashlib.sha1()
    for ch in chapters:
        cid = (ch.get("id") or "").encode("utf-8", "ignore")
        txt = (ch.get("content") or "").encode("utf-8", "ignore")
        h.update(cid + b"|" + str(len(txt)).encode("ascii") + b";")
    return h.hexdigest()[:12]

# ----------------- EXPORT CORE -----------------
def build_book_pdf_kdp(book_title:str, author:str, chapters:List[Dict],
                       trim:str="6x9", bleed:bool=False,
                       outer_margin_in:float=0.5, top_bottom_in:float=0.5) -> Tuple[bytes,int,bool]:
    """
    Genera PDF:
      - trim e bleed opzionali
      - font TTF embedded (se disponibile)
      - gutter KDP e margini specchiati
    Ritorna: (pdf_bytes, page_count, fonts_embedded)
    """
    page_w, page_h = TRIMS.get(trim, TRIMS["6x9"])
    bleed_add = (0.125*INCH if bleed else 0.0)
    page_size = (page_w + 2*bleed_add, page_h + 2*bleed_add)

    font_name, embedded = _register_ttf()
    styles = _styles(font_name)

    # Pre-story (stima pagine senza gutter)
    prelim = _make_story(book_title, author, chapters, styles)
    prelim_margins = dict(
        left=(outer_margin_in*INCH)+bleed_add,
        right=(outer_margin_in*INCH)+bleed_add,
        top=(top_bottom_in*INCH)+bleed_add,
        bottom=(top_bottom_in*INCH)+bleed_add,
    )
    _, prelim_pages = _build_pdf_mirror(page_size, prelim_margins, prelim)
    prelim_pages = max(24, prelim_pages or 24)  # “minimo editoriale” ragionevole

    # Gutter in base alle pagine
    gutter = _kdp_gutter(prelim_pages)

    # Margini finali: aggiungiamo il gutter al “lato interno”, ottenuto col mirroring
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
                              classic: bool = False,
                              cache_to_disk: bool = True):
    """
    Esporta l'intero libro in PDF.
    - trim: 6x9 | 5x8 | 8.5x11
    - bleed: true/false
    - classic: true -> A4, margini standard 2cm, nessun gutter
    - cache_to_disk: salva anche su /static/books/{book_id}_kdp_*.pdf
    """
    # 1) Carica indice libri (sempre da disco per coerenza)
    try:
        all_books = storage.load_books_from_disk()
    except Exception:
        all_books = getattr(storage, "BOOKS_CACHE", []) or []

    # Alcuni ambienti possono avere “stray” records non-dict (vedi log con curl)
    safe_books = [b for b in (all_books or []) if isinstance(b, dict)]
    meta = next((b for b in safe_books if (b.get("id") or b.get("book_id")) == book_id), None)
    if not meta:
        raise HTTPException(status_code=404, detail="Libro non trovato.")

    ch_list = meta.get("chapters") or []
    if not ch_list:
        raise HTTPException(status_code=404, detail="Nessun capitolo nel libro.")

    # 2) Carica contenuti capitoli da DISCO
    chapters_full = []
    for ch in ch_list:
        if not isinstance(ch, dict):  # ignora elementi corrotti
            continue
        cid = ch.get("id") or ch.get("chapter_id")
        if not cid:
            continue
        text = _read_chapter_file(book_id, cid)
        if not text and hasattr(storage, "read_chapter_text"):
            try: text = storage.read_chapter_text(book_id, cid) or ""
            except Exception: text = ""
        chapters_full.append({"id": cid, "title": ch.get("title") or cid, "content": text})

    if not chapters_full:
        raise HTTPException(status_code=404, detail="Impossibile assemblare i capitoli.")

    # 3) Classic (A4 semplice) oppure KDP
    if classic:
        font_name, embedded = _register_ttf()
        styles = _styles(font_name)
        buffer = io.BytesIO()
        doc = BaseDocTemplate(
            buffer, pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
            title=meta.get("title") or "EccomiBook"
        )
        frame = Frame(2*cm, 2*cm, A4[0]-4*cm, A4[1]-4*cm)
        doc.addPageTemplates([PageTemplate(id='a4', frames=[frame])])
        doc.build(_make_story(meta.get("title") or book_id, meta.get("author") or "", chapters_full, styles))
        pdf_bytes = buffer.getvalue(); buffer.close()
        pages = doc.page
        embedded = (font_name != "Helvetica")
        # opzionale cache A4 su disco? al momento no.
        headers = {
            "Content-Disposition": f'attachment; filename="{(meta.get("title") or book_id).replace(" ","_")}_A4.pdf"',
            "X-Pages": str(pages),
            "X-Fonts-Embedded": "yes" if embedded else "no"
        }
        return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)

    # 4) KDP-ready
    pdf_bytes, pages, embedded = build_book_pdf_kdp(
        book_title = meta.get("title") or book_id,
        author     = meta.get("author") or "",
        chapters   = chapters_full,
        trim       = trim,
        bleed      = bleed,
        outer_margin_in    = outer_margin,
        top_bottom_in      = top_bottom_margin
    )

    # 5) Cache su DISCO (per avere link fisso in /static/books)
    # filename: {book_id}_kdp_{trim}{_bleed}_{sig}.pdf  (sig = firma contenuti)
    headers = {
        "X-KDP-Pages": str(pages),
        "X-Fonts-Embedded": "yes" if embedded else "no"
    }

    if cache_to_disk:
        try:
            sig = _content_signature(chapters_full)
            suffix = f"{trim}{'_bleed' if bleed else ''}_{sig}"
            fname = f"{(meta.get('title') or book_id).replace(' ','_')}_kdp_{suffix}.pdf"
            out_path = storage.BOOKS_DIR / fname
            storage.BOOKS_DIR.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(pdf_bytes)

            # rispondi servendo il file dal disco (beneficia di etag/length ecc.)
            headers.update({
                "X-File-Path": str(out_path),
                "Cache-Control": "no-cache",
            })
            return FileResponse(path=out_path, media_type="application/pdf",
                                filename=fname, headers=headers)
        except Exception:
            # se fallisce il salvataggio, ripiega sullo stream diretto
            pass

    # fallback: stream diretto
    dl_name = f"{(meta.get('title') or book_id).replace(' ','_')}_kdp_{trim}{'_bleed' if bleed else ''}.pdf"
    headers.update({
        "Content-Disposition": f'attachment; filename="{dl_name}"',
        "Cache-Control": "no-cache",
    })
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


@router.get("/books/{book_id}/export/md", response_class=PlainTextResponse, name="Export Book Md")
@router.get("/books/{book_id}/export/txt", response_class=PlainTextResponse, name="Export Book Txt")
async def export_book_text(request: Request, book_id: str):
    """
    Esporta il libro come Markdown/TXT, leggendo i testi da disco.
    """
    try:
        all_books = storage.load_books_from_disk()
    except Exception:
        all_books = getattr(storage, "BOOKS_CACHE", []) or []
    safe_books = [b for b in (all_books or []) if isinstance(b, dict)]
    meta = next((b for b in safe_books if (b.get("id") or b.get("book_id")) == book_id), None)
    if not meta:
        raise HTTPException(status_code=404, detail="Libro non trovato.")
    ch_list = meta.get("chapters") or []
    if not ch_list:
        raise HTTPException(status_code=404, detail="Nessun capitolo nel libro.")

    chunks = [f"# {meta.get('title') or book_id}\n\nAutore: {meta.get('author') or '—'}\n"]
    for ch in ch_list:
        if not isinstance(ch, dict):
            continue
        cid = ch.get("id") or ch.get("chapter_id")
        if not cid:
            continue
        t = ch.get("title") or cid
        txt = _read_chapter_file(book_id, cid)
        if not txt and hasattr(storage, "read_chapter_text"):
            try:
                txt = storage.read_chapter_text(book_id, cid) or ""
            except Exception:
                txt = ""
        chunks.append(f"\n\n# {t}\n\n{txt}")
    body = "".join(chunks)
    return PlainTextResponse(body, media_type="text/markdown; charset=utf-8")
