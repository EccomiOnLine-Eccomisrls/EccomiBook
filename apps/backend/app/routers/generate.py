# apps/backend/routes/generate.py (estratto)
from fastapi import APIRouter, Header, HTTPException, Request, Body
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from textwrap import wrap
import time
import uuid

from ..models import GenChapterIn, GenChapterOut
from ..settings import get_settings
from .. import storage  # se non lo usi, puoi rimuoverlo

router = APIRouter()


def _auth_or_403(x_api_key: str | None):
    settings = get_settings()
    if settings.x_api_key and x_api_key != settings.x_api_key:
        raise HTTPException(status_code=403, detail="Chiave API non valida")


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

    usable_width = width - left_margin - right_margin
    line_height_title = 16
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
        abstract_lines = wrap(abstract, width=90)  # wrap "blando" per corsivo
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
        # separatore
        y -= 0.5 * cm

    # --- Contenuto ---
    c.setFont("Helvetica", 12)

    # Wrap del contenuto su una larghezza ragionevole (approssimazione monospace)
    # Per maggiore precisione potresti misurare con stringWidth, ma per MVP va bene.
    body_lines = []
    for para in content.split("\n"):
        para = para.strip()
        if not para:
            body_lines.append("")  # riga vuota
            continue
        body_lines.extend(wrap(para, width=95))  # ~95 char per riga a Helvetica 12 su A4 con margini dati

    for line in body_lines:
        if y <= bottom_margin:
            if page_numbers:
                _draw_footer_page_number(c, page_num, left_margin, bottom_margin)
            c.showPage()
            page_num += 1
            y = height - top_margin
            c.setFont("Helvetica", 12)
        if line == "":
            y -= line_height_body  # riga vuota = salto
        else:
            c.drawString(left_margin, y, line)
            y -= line_height_body

    # footer ultima pagina
    if page_numbers:
        _draw_footer_page_number(c, page_num, left_margin, bottom_margin)

    c.save()


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
    # Se non hai ancora la generazione AI del contenuto, usa outline/prompt come base.
    base_content = payload.outline or payload.prompt or ""
    if not base_content:
        base_content = "Contenuto capitolo non fornito. (MVP placeholder)"

    # Abstract: lo prendiamo dall'input se c’è; in alternativa potresti generarlo.
    abstract = payload.abstract

    # 2) ID & path PDF
    chapter_id = f"ch_{uuid.uuid4().hex[:8]}"
    output_dir = Path("storage") / "chapters"
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{chapter_id}.pdf"

    # 3) Render PDF con numerazione on/off
    _render_chapter_pdf(
        pdf_path,
        title=title,
        content=base_content,
        abstract=abstract,
        page_numbers=bool(payload.page_numbers),
    )

    # 4) URL pubblico/servito
    # Adatta questa logica alla tua infrastruttura (Nginx/StaticFiles/Cloud storage).
    # Se già esiste un tuo modulo `storage`, puoi salvarlo lì e ottenere l’URL.
    # Per MVP locale:
    pdf_url = f"/static/chapters/{chapter_id}.pdf"  # esponi 'storage/chapters' come /static/chapters

    # 5) Output coerente con lo schema
    return GenChapterOut(
        chapter_id=chapter_id,
        title=title,
        content=base_content,
        abstract=abstract,
        page_numbers=bool(payload.page_numbers),
    )
