from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Dict
from uuid import uuid4
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, PageBreak
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet

from models import BookCreate, BookOut, ChapterCreate, ChapterOut

app = FastAPI(title="EccomiBook Backend", version="0.1.0")

# In-memory storage
BOOKS: Dict[str, dict] = {}


# -------------------------
# HELPERS
# -------------------------
def _render_book_pdf_to_memory(book: dict) -> BytesIO:
    """Crea PDF da un libro (in memoria)"""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=book.get("title") or "EccomiBook",
        author=book.get("author") or "Eccomi Online",
    )
    styles = getSampleStyleSheet()
    story = []

    # Copertina
    story.append(Paragraph(book.get("title", "EccomiBook"), styles["Title"]))
    meta = []
    if book.get("author"):
        meta.append(f"Autore: {book['author']}")
    if book.get("language"):
        meta.append(f"Lingua: {book['language']}")
    if book.get("genre"):
        meta.append(f"Genere: {book['genre']}")
    if meta:
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(" • ".join(meta), styles["Normal"]))
    if book.get("description"):
        story.append(Spacer(1, 0.6 * cm))
        story.append(Paragraph(book["description"], styles["BodyText"]))
    story.append(PageBreak())

    # Capitoli
    chapters = book.get("chapters") or []
    for idx, ch in enumerate(chapters, start=1):
        title = ch.get("title") or f"Capitolo {idx}"
        outline = ch.get("outline") or ""
        story.append(Paragraph(title, styles["Heading1"]))
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(outline.replace("\n", "<br/>"), styles["BodyText"]))
        if idx < len(chapters):
            story.append(PageBreak())

    doc.build(story)
    buf.seek(0)
    return buf


# -------------------------
# ENDPOINTS
# -------------------------

@app.get("/health")
def health():
    return {"status": "ok", "service": "EccomiBook Backend"}


@app.get("/books", response_model=list[BookOut])
def list_books():
    return list(BOOKS.values())


@app.post("/books", response_model=BookOut)
def create_book(book: BookCreate):
    book_id = f"book_{uuid4().hex[:6]}"
    new_book = book.dict()
    new_book["id"] = book_id
    new_book["plan"] = "owner_full"
    new_book["chapters"] = []
    BOOKS[book_id] = new_book
    return new_book


@app.post("/books/{book_id}/chapters", response_model=ChapterOut)
def add_chapter(book_id: str, chapter: ChapterCreate):
    book = BOOKS.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    ch_id = f"ch_{uuid4().hex[:6]}"
    new_ch = chapter.dict()
    new_ch["id"] = ch_id
    book["chapters"].append(new_ch)
    return new_ch


@app.put("/books/{book_id}/chapters/{chapter_id}", response_model=ChapterOut)
def update_chapter(book_id: str, chapter_id: str, chapter: ChapterCreate):
    book = BOOKS.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    for ch in book["chapters"]:
        if ch["id"] == chapter_id:
            ch.update(chapter.dict())
            return ch
    raise HTTPException(status_code=404, detail="Capitolo non trovato")


@app.get("/generate/export/book/{book_id}/download")
def export_book_download(
    book_id: str,
    format: str = Query("pdf", pattern="^(?i:pdf)$"),
):
    book = BOOKS.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    if not book.get("chapters"):
        raise HTTPException(status_code=400, detail="Nessun capitolo da esportare")

    if format.lower() != "pdf":
        raise HTTPException(status_code=400, detail="Formato non supportato (solo pdf)")

    pdf_io = _render_book_pdf_to_memory(book)
    filename = f"{book_id}.pdf"
    return StreamingResponse(
        pdf_io,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
