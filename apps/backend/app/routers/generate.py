from fastapi import APIRouter, Header, HTTPException, Request, Body, Depends
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from textwrap import wrap
import uuid

from ..models import GenChapterIn, GenChapterOut
from ..settings import get_settings
from .. import storage                     # path/URL persistenti
from .. import ai                          # generazione AI

# dipendenze/piani (salgo di due livelli: app/routers -> backend)
from ..deps import get_current_user
from ..plans import PLANS

router = APIRouter()

def _auth_or_403(x_api_key: str | None):
    settings = get_settings()
    if settings.x_api_key and x_api_key != settings.x_api_key:
        raise HTTPException(status_code=403, detail="Chiave API non valida")

# -------------------------------
# Helpers: capitolo singolo (PDF)
# -------------------------------

def _draw_footer_page_number(c: canvas.Canvas, page_num: int, left_margin: float, bottom_margin: float):
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
    width, height = A4
    left_margin = 2.2 * cm
    right_margin = 2.2 * cm
    top_margin = 2.2 * cm
    bottom_margin = 2.2 * cm
    line_height_body = 13

    c = canvas.Canvas(str(output_path), pagesize=A4)

    page_num = 1
    y = height - top_margin

    # Titolo
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left_margin, y, title)
    y -= 1.0 * cm

    # Abstract (opzionale)
    if abstract:
        c.setFont("Helvetica-Oblique", 11)
        for line in wrap(abstract, width=90):
            if y <= bottom_margin:
                if page_numbers:
                    _draw_footer_page_number(c, page_num, left_margin, bottom_margin)
                c.showPage(); page_num += 1
                y = height - top_margin
                c.setFont("Helvetica-Oblique", 11)
            c.drawString(left_margin, y, line)
            y -= line_height_body
        y -= 0.5 * cm

    # Contenuto
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
            c.showPage(); page_num += 1
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

    # Pagina del titolo
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width / 2, height - 5 * cm, book_title)
    if author:
        c.setFont("Helvetica-Oblique", 14)
        c.drawCentredString(width / 2, height - 6 * cm, f"di {author}")
    c.showPage()

    # Capitoli
    for ch in chapters:
        title = (ch.get("title") or "").strip() or "Capitolo"
        content = (ch.get("outline") or ch.get("prompt") or "").strip() or "(contenuto non disponibile)"

        y = height - top_margin
        c.setFont("Helvetica-Bold", 16)
        c.drawString(left_margin, y, title)
        y -= 0.8 * cm

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
    user = Depends(get_current_user),  # ← utente autenticato (porta piano & quota)
):
    _auth_or_403(x_api_key)

    # Regole del piano + quota
    rules = PLANS.get((user.plan or "START").upper(), PLANS["START"])
    if rules.monthly_chapter_quota is not None and user.quota_monthly_used >= rules.monthly_chapter_quota:
        raise HTTPException(status_code=429, detail="Quota mensile esaurita per il tuo piano")

    # Input
    title = payload.title
    prompt = payload.prompt or ""
    outline = payload.outline or ""
    abstract = payload.abstract

    # Contenuto AI in base al piano
    base_content = ai.generate_chapter_text(
        title=title,
        prompt=prompt,
        outline=outline,
        plan=user.plan,
    )

    # ID e salvataggio su disco persistente
    chapter_id = f"ch_{uuid.uuid4().hex[:8]}"
    pdf_filename = f"chapters/{chapter_id}.pdf"
    pdf_path = storage.file_path(pdf_filename)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    _render_chapter_pdf(
        pdf_path,
        title=title,
        content=base_content,
        abstract=abstract,
        page_numbers=bool(payload.page_numbers),
    )

    # Aggiorna quota utente
    user.quota_monthly_used += 1
    try:
        from ...users import save_users
        save_users()
    except Exception:
        pass  # se non esistono utenti persistenti, ignora

    # URL assoluto
    base_url = str(request.base_url).rstrip("/")
    pdf_url = f"{base_url}/static/chapters/{chapter_id}.pdf"

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
    user = Depends(get_current_user),
):
    _auth_or_403(x_api_key)

    # Check permesso dal piano
    rules = PLANS.get((user.plan or "START").upper(), PLANS["START"])
    if not rules.allow_export_book:
        raise HTTPException(status_code=403, detail="Il tuo piano non consente l'export del libro")

    # Recupera libro
    app_state = request.app.state
    books_db = getattr(app_state, "books", {})
    book = books_db.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    book_title = book.get("title") or f"Libro {book_id}"
    author = book.get("author")
    chapters = book.get("chapters") or []
    if not chapters:
        raise HTTPException(status_code=400, detail="Nessun capitolo presente nel libro")

    # Salva su disco persistente
    pdf_filename = f"books/{book_id}.pdf"
    pdf_path = storage.file_path(pdf_filename)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    _render_book_pdf(
        pdf_path,
        book_title=book_title,
        author=author,
        chapters=chapters,
    )

    # URL di download via /downloads
    base = str(request.base_url).rstrip("/")
    download_url = f"{base}/downloads/{pdf_filename}"

    return {
        "book_id": book_id,
        "title": book_title,
        "author": author,
        "chapters_count": len(chapters),
        "download_url": download_url,
    }
