from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from app.ai import (
    current_caps,
    ensure_can_add_chapter,
    ensure_can_export,
)
from app.models import ChapterCreate, ChapterOut
from app import storage

router = APIRouter(prefix="", tags=["Generate"])


@router.post("/generate/chapter", response_model=ChapterOut)
def generate_chapter(
    body: ChapterCreate,
    book_id: str | None = Query(None, description="Se presente, aggiunge il capitolo a questo libro"),
    caps=Depends(current_caps),
):
    """
    Genera un capitolo testuale (stub di AI).
    - Se book_id è passato: applica i limiti capitoli/giorno e salva nel libro.
    - Se book_id è assente: restituisce solo il contenuto generato (non salva).
    """
    # Nota: qui potresti chiamare la tua pipeline AI vera. Per ora stub.
    generated = storage.generate_chapter_stub(body)

    if book_id:
        if not storage.get_book(book_id):
            raise HTTPException(status_code=404, detail="Libro non trovato")
        # limiti piano (capitoli/giorno)
        ensure_can_add_chapter(caps)
        saved = storage.add_chapter(book_id, generated)
        storage.inc_chapter(caps.user_id)
        return saved

    return generated


@router.get("/generate/export/book/{book_id}")
def export_book(
    book_id: str,
    format: str = Query("pdf", enum=["pdf", "epub", "docx"]),
    caps=Depends(current_caps),
):
    """
    Export del libro (PDF/ePub/DOCX).
    - Applica i permessi di export del piano.
    - Qui usiamo uno stub che produce un payload finto/URL temporaneo.
    """
    if not storage.get_book(book_id):
        raise HTTPException(status_code=404, detail="Libro non trovato")

    ensure_can_export(format, caps)
    payload = storage.export_book_stub(book_id, format=format)

    # Puoi sostituire con StreamingResponse di un file vero quando vuoi
    return JSONResponse(payload)
