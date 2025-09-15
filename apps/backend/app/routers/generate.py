# app/routers/generate.py
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import FileResponse
from typing import Optional
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import os

from app.models import GenerateChapterIn, ChapterOut, Plan, PLAN_CAPS
from app.storage import DB, new_id, reset_daily_if_needed

router = APIRouter(prefix="/generate", tags=["Generate"])


def get_plan_and_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> tuple[Plan, Optional[str]]:
    if x_api_key and x_api_key.startswith("owner_"):
        return (Plan.OWNER_FULL, x_api_key)
    return (Plan.START, x_api_key)


@router.post("/chapter", response_model=ChapterOut)
def generate_chapter(body: GenerateChapterIn, data=Depends(get_plan_and_key)):
    plan, api_key = data
    caps = PLAN_CAPS[plan]

    # rate limit basilare al giorno
    if api_key:
        counter = DB["limits"].setdefault(api_key, {})
        reset_daily_if_needed(counter)
        if caps["max_chapters_per_day"] is not None and counter.get("chapters_today", 0) >= caps["max_chapters_per_day"]:
            raise HTTPException(status_code=429, detail="Limite capitoli giornalieri raggiunto")
        counter["chapters_today"] = counter.get("chapters_today", 0) + 1

    book = DB["books"].get(body.book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    # MOCK AI: testo semplice basato sul prompt
    generated_text = f"Capitolo generato su: {body.prompt}\n\n" \
                     f"Testo di esempio. (Sostituire con AI reale)."

    chap_id = new_id("ch")
    chapter = {
        "id": chap_id,
        "title": f"Capitolo su {body.prompt[:30]}",
        "order": len(book["chapters"]) + 1,
        "content": generated_text,
        "images": [f"https://placehold.co/800x600?text={i+1}" for i in range(max(0, body.images))],
    }
    DB["chapters"][chap_id] = chapter
    book["chapters"].append(chapter)
    return chapter


@router.get("/export/book/{book_id}")
def export_book_pdf(book_id: str):
    """Export minimale in PDF (solo testo)."""
    book = DB["books"].get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    path = f"/tmp/{book_id}.pdf"
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4

    def write_paragraph(txt: str, x=50, y_start=800, leading=14):
        y = y_start
        for line in txt.split("\n"):
            if y < 60:
                c.showPage()
                y = 800
            c.drawString(x, y, line[:110])
            y -= leading

    c.setTitle(book["title"])
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 800, book["title"])
    c.setFont("Helvetica", 10)
    c.drawString(50, 780, f"Language: {book['language']} | Genre: {book['genre']}")
    c.showPage()

    for ch in book["chapters"]:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, 800, f"{ch['order']}. {ch['title']}")
        c.setFont("Helvetica", 11)
        write_paragraph(ch["content"], x=50, y_start=770, leading=14)
        c.showPage()

    c.save()
    return FileResponse(path, media_type="application/pdf", filename=f"{book['title']}.pdf")
