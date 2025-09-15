from fastapi import APIRouter, Header, HTTPException, Request, Body
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from textwrap import wrap
import uuid

from ..models import GenChapterIn, GenChapterOut
from ..settings import get_settings
from .. import storage  # se non lo usi, puoi rimuoverlo

router = APIRouter()


def _auth_or_403(x_api_key: str | None):
    settings = get_settings()
    if settings.x_api_key and x_api_key != settings.x_api_key:
        raise HTTPException(status_code=403, detail="Chiave API non valida")


# -------------------------------
# Helpers: capitolo singolo (PDF)
# -------------------------------

def _draw_footer_page_number(c: canvas.Canvas, page_num: int, left_margin: float, bottom_margin: float):
    """Scrive il numero pagina nel footer (es. 'Pag. 1')."""
    footer_text = f"Pag. {page_num}"
    c.setFont("Helvetica", 9)
    c.drawString(left_margin, bottom_margin - 0.5 * cm, footer_text)


def _render_chapter_pdf(
    output_path: Path,
    *,
    title: str,
    content: str,
    abstract: str | None,
    page_numbers: bool,
):
    """Crea un PDF A4 con titolo, (eventuale) abstract e contenuto con word-wrap & salto pagina."""
    width, height = A4
    left_margin = 2.2 * cm
    right_margin = 2.2 * cm
    top_margin = 2.2 * cm
    bottom_margin = 2.2 * cm

    line_height_body = 13

    c = canvas.Canvas(str(output_path), pagesize=A4)

    page_num = 1

    # --- Header: Titolo ---
    y = height - top_margin
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left_margin, y, title)
    y -= 1.0 * cm  # spazio dopo titolo

    # --- Abstract (opzionale) ---
    if abstract:
        c.setFont("Helvetica-Oblique", 11)
        abstract_lines = wrap(abstract, width=90)
        for line in abstract_lines:
            if y <= bottom_margin:
                if page_numbers:
                    _draw_footer_page_number(c, page_num, left_margin, bottom_margin)
                c.showPage()
                page_num += 1
                y = height - top_margin
                c.setFont("Helvetica-Oblique", 11)
            c.drawString(left_margin, y, line)
            y -= line_height_body
        y -= 0.5 * cm

    # --- Contenuto ---
    c.setFont("Helvetica", 12)
    body_lines = []
    for para in content.split("\n"):
        para = para.strip()
        if not para:
            body_lines.append("")
            continue
        body_lines.extend(wrap(para, width=95))

    for line in body_lines:
        if y <= bottom_margin:
            if page_numbers:
                _draw_footer_page_number(c, page_num, left_margin, bottom_margin)
            c.showPage()
            page_num += 1
            y = height - top_margin
            c.setFont("Helvetica", 12)
        if line == "":
            y -= line_height_body
        else:
            c.drawString(left_margin, y, line)
            y -= line_height_body

    if page_numbers:
        _draw_footer_page_number(c, page_num, left_margin, bottom_margin)

    c.save()


# --------------------------------------
# Helpers: export libro intero (unico PDF)
# --------------------------------------

def _render_book_pdf(
    output_path: Path,
    *,
    book_title: str,
    author: str | None,
    chapters: list[dict],
):
    """Crea un PDF libro unico con pagina titolo e capitoli (usa outline o prompt come contenuto)."""
    width, height = A4
    left_margin = 2.2 * cm
    right_margin = 2.2 * cm
    top_margin = 2.2 * cm
    bottom_margin = 2.2 * cm
    line_h = 14

    c = canvas.Canvas(str(output_path), pagesize=A4)

    # --- Pagina del titolo ---
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width / 2, height - 5 * cm, book_title)
    if author:
        c.setFont("Helvetica-Oblique", 14)
        c.drawCentredString(width / 2, height - 6 * cm, f"di {author}")
    c.showPage()

    # --- Capitoli ---
    for ch in chapters:
        title = (ch.get("title") or "").strip() or "Capitolo"
        content = (ch.get("outline") or ch.get("prompt") or "").strip() or "(contenuto non disponibile)"

        # Titolo capitolo
        y = height - top_margin
        c.setFont("Helvetica-Bold", 16)
        c.drawString(left_margin, y, title)
        y -= 0.8 * cm

        # Corpo
        c.setFont("Helvetica", 12)
        lines = []
        for para in content.split("\n"):
            para = para.strip()
            if not para:
                lines.append("")
                continue
            lines.extend(wrap(para, width=95))

        for line in lines:
            if y <= bottom_margin:
                c.showPage()
                y = height - top_margin
                c.setFont("Helvetica", 12)
            if line == "":
                y -= line_h
            else:
                c.drawString(left_margin, y, line)
                y -= line_h

        c.showPage()

    c.save()


# -------------------------------
# Routes
# -------------------------------

@router.post(
    "/generate/chapter",
    summary="Generate Chapter",
    response_model=GenChapterOut,
)
def generate_chapter(
    request: Request,
    payload: GenChapterIn = Body(...),
    x_api_key: str | None = Header(default=None),
):
    _auth_or_403(x_api_key)

    # 1) Recupero input
    title = payload.title
    base_content = payload.outline or payload.prompt or ""
    if not base_content:
        base_content = "Contenuto capitolo non fornito. (MVP placeholder)"

    abstract = payload.abstract

    # 2) ID & path PDF
    chapter_id = f"ch_{uuid.uuid4().hex[:8]}"
    output_dir = Path("storage") / "chapters"
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{chapter_id}.pdf"

    # 3) Render PDF
    _render_chapter_pdf(
        pdf_path,
        title=title,
        content=base_content,
        abstract=abstract,
        page_numbers=bool(payload.page_numbers),
    )

    # 4) URL pubblico/servito (assoluto)
    base_url = str(request.base_url).rstrip("/")
    pdf_url = f"{base_url}/static/chapters/{chapter_id}.pdf"

    # 5) Output coerente con lo schema
    return GenChapterOut(
        chapter_id=chapter_id,
        title=title,
        content=base_content,
        abstract=abstract,
        page_numbers=bool(payload.page_numbers),
        pdf_url=pdf_url,
    )


@router.post(
    "/generate/export/book/{book_id}",
    summary="Export entire book as a single PDF",
    tags=["default"],
)
def export_book_pdf(
    request: Request,
    book_id: str,
    x_api_key: str | None = Header(default=None),
):
    _auth_or_403(x_api_key)

    # Recupera libro dal piccolo DB in memoria
    app_state = request.app.state
    books_db = getattr(app_state, "books", {})
    book = books_db.get(book_id)

    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    # Estraggo dati minimi
    book_title = book.get("title") or f"Libro {book_id}"
    author = book.get("author")
    chapters = book.get("chapters") or []  # atteso elenco di dict con title/prompt/outline

    if not chapters:
        raise HTTPException(status_code=400, detail="Nessun capitolo presente nel libro")

    # Path export
    books_dir = Path("storage") / "books"
    books_dir.mkdir(parents=True, exist_ok=True)
    pdf_filename = f"{book_id}.pdf"
    pdf_path = books_dir / pdf_filename

    # Render PDF unico
    _render_book_pdf(
        pdf_path,
        book_title=book_title,
        author=author,
        chapters=chapters,
    )

    # Link di download tramite la route /downloads/{filename}
    # NB: la tua /downloads/{filename} usa storage.file_path(filename),
    # quindi passiamo "books/<file>.pdf" come 'filename' dinamico.
    download_url = f"/downloads/books/{pdf_filename}"

    return {
        "book_id": book_id,
        "title": book_title,
        "author": author,
        "chapters_count": len(chapters),
        "download_url": download_url,
    }
