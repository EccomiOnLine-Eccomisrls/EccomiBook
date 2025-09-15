from fastapi import APIRouter, Header, HTTPException, Request, Body, Query
from typing import Dict, Any, Literal, List
from pathlib import Path
import time

# reportlab (impaginazione con Paragraph per evitare frasi spezzate)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from ..models import GenChapterIn, GenChapterOut
from ..settings import get_settings
from .. import storage

router = APIRouter()


def _auth_or_403(x_api_key: str | None):
    settings = get_settings()
    if settings.x_api_key and x_api_key != settings.x_api_key:
        raise HTTPException(status_code=403, detail="Chiave API non valida")


@router.post("/generate/chapter", summary="Generate Chapter", response_model=GenChapterOut)
def generate_chapter(
    request: Request,
    payload: GenChapterIn = Body(...),
    x_api_key: str | None = Header(default=None),
):
    _auth_or_403(x_api_key)

    # mock “AI”: crea testo semplice usando prompt/outline
    txt_lines: List[str] = []
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
            {"id": ch_id, "title": payload.title, "prompt": payload.prompt or "", "outline": payload.outline or ""}
        )
        return GenChapterOut(chapter_id=ch_id, title=payload.title, content=content)

    return GenChapterOut(chapter_id=None, title=payload.title, content=content)


@router.get("/generate/export/book/{book_id}", summary="Export Book")
def export_book(
    request: Request,
    book_id: str,
    format: Literal["pdf", "docx", "epub"] = Query("pdf"),
    page_numbers: bool = Query(True, description="Se True aggiunge la numerazione di pagina"),
    x_api_key: str | None = Header(default=None),
):
    """
    Genera un file del libro (PDF reale; DOCX/EPUB placeholder per MVP).
    - Niente frasi spezzate: il testo è unito e impaginato con Paragraph.
    - Abstract opzionale se presente nel libro.
    - Numeri di pagina facoltativi (page_numbers=true/false).
    """
    _auth_or_403(x_api_key)
    books: Dict[str, Dict[str, Any]] = request.app.state.books
    if book_id not in books:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    book = books[book_id]
    filename = f"{book_id}.{format}"

    if format == "pdf":
        out_path: Path = storage.file_path(filename)

        doc = SimpleDocTemplate(
            str(out_path),
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            title=book["title"],
            author=book["author"],
        )

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="TitleBig", parent=styles["Title"], fontSize=20, leading=24, spaceAfter=8))
        styles.add(ParagraphStyle(name="Meta", parent=styles["Normal"], fontSize=9, textColor="#444444", spaceAfter=14))
        styles.add(ParagraphStyle(name="H1", parent=styles["Heading1"], fontSize=14, leading=18, spaceBefore=12, spaceAfter=6))
        styles.add(ParagraphStyle(name="Body", parent=styles["Normal"], fontSize=11, leading=15))

        def _number_canvas(canv, doc_):
            canv.saveState()
            canv.setFont("Helvetica", 9)
            canv.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"{doc_.page}")
            canv.restoreState()

        story: List = []
        # Titolo
        story.append(Paragraph(book["title"], styles["TitleBig"]))
        meta = f"Autore: {book['author']}  •  Lingua: {book['language']}  •  Genere: {book['genre']}"
        story.append(Paragraph(meta, styles["Meta"]))

        # Abstract (se presente)
        abstract = (book.get("abstract") or "").strip()
        if abstract:
            story.append(Paragraph("<b>Abstract</b>", styles["H1"]))
            story.append(Paragraph(abstract.replace("\n", "<br/>"), styles["Body"]))
            story.append(Spacer(1, 12))

        # Descrizione (se diversa da abstract)
        descr = (book.get("description") or "").strip()
        if descr and descr != abstract:
            story.append(Paragraph("<b>Descrizione</b>", styles["H1"]))
            story.append(Paragraph(descr.replace("\n", "<br/>"), styles["Body"]))
            story.append(Spacer(1, 12))

        # Capitoli
        for i, ch in enumerate(book.get("chapters", []), start=1):
            title = ch.get("title") or f"Capitolo {i}"
            body = (ch.get("outline") or ch.get("prompt") or "").strip()

            story.append(Paragraph(f"{i}. {title}", styles["H1"]))
            if body:
                story.append(Paragraph(body.replace("\n", "<br/>"), styles["Body"]))
            story.append(Spacer(1, 10))

        if page_numbers:
            doc.build(story, onFirstPage=_number_canvas, onLaterPages=_number_canvas)
        else:
            doc.build(story)

    else:
        # placeholder per mvp
        storage.file_path(filename).write_text(f"{format.upper()} export placeholder for {book_id}\n")

    url = storage.public_url(filename)
    return {
        "ok": True,
        "book_id": book_id,
        "format": format,
        "file_name": filename,
        "url": url,
        "chapters": len(book.get("chapters", [])),
        "generated_at": int(time.time()),
    }
