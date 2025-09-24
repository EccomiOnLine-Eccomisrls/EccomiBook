# apps/backend/app/routers/books.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from typing import Dict, List, Any
from pathlib import Path
from datetime import datetime
import io

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet

from app import storage

router = APIRouter()

# ----------------------------- Models ----------------------------- #

class BookIn(BaseModel):
    title: str
    author: str | None = None
    abstract: str | None = None
    description: str | None = None
    genre: str | None = None
    language: str = "it"
    plan: str | None = None
    chapters: List[Dict[str, Any]] = []


class ChapterUpdate(BaseModel):
    content: str


# --------------------------- Helpers FS --------------------------- #

def _book_dir(book_id: str) -> Path:
    return storage.BASE_DIR / "chapters" / book_id

def _chapter_path(book_id: str, chapter_id: str) -> Path:
    """Preferisci .md, altrimenti .txt."""
    base = _book_dir(book_id)
    md = base / f"{chapter_id}.md"
    if md.exists():
        return md
    return base / f"{chapter_id}.txt"

def _scan_chapters_from_disk(book_id: str) -> List[Dict[str, Any]]:
    """
    Ritorna elenco capitoli presenti su disco con id, title, updated_at, path.
    Tiene md/txt e deduplica per stem.
    """
    base = _book_dir(book_id)
    if not base.exists():
        return []
    items: Dict[str, Dict[str, Any]] = {}

    files = list(base.glob("*.md")) + list(base.glob("*.txt"))
    for p in files:
        cid = p.stem
        ts = datetime.utcfromtimestamp(p.stat().st_mtime).isoformat()
        rec = items.get(cid)
        if rec is None or ts > rec["updated_at"]:
            items[cid] = {
                "id": cid,
                "title": cid,
                "updated_at": ts,
                "path": p.as_posix(),
            }

    def _sort_key(c: Dict[str, Any]):
        try:
            # ordina ch_0001, ch_0002, ...; fallback al testo
            return int(str(c["id"]).split("_", 1)[1])
        except Exception:
            return c["id"]

    return sorted(items.values(), key=_sort_key)

def _load_books_list() -> List[Dict[str, Any]]:
    """
    Carica i libri dal disco; supporta sia formato list che {"items":[...]}.
    """
    try:
        raw = storage.load_books_from_disk()
    except Exception:
        raw = []

    items = raw.get("items") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        items = []
    # normalizza id
    for b in items:
        if isinstance(b, dict) and "id" not in b and "book_id" in b:
            b["id"] = b.get("book_id")
    return items

def _save_books_list(items: List[Dict[str, Any]]) -> None:
    # se il tuo storage si aspetta un plain list, salva direttamente;
    # se vuole {"items":[...]}, adatta qui.
    storage.save_books_to_disk(items)

def _coalesce_book_stats(book: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ritorna il dict libro arricchito con:
    - chapters: popolati da disco se mancanti
    - chapters_count
    - updated_at
    """
    if not isinstance(book, dict):
        return {}
    book_id = book.get("id") or book.get("book_id") or ""
    chapters = book.get("chapters") or []

    if not chapters:
        chapters = _scan_chapters_from_disk(book_id)

    chapters_count = len(chapters)
    last_upd = ""
    if chapters:
        last_upd = max((c.get("updated_at") or "") for c in chapters if isinstance(c, dict)) or ""

    return {
        **book,
        "id": book_id,
        "chapters": chapters,
        "chapters_count": chapters_count,
        "updated_at": last_upd,
    }

# ---------------------------- Endpoints --------------------------- #

@router.get("/books", summary="List Books")
def list_books():
    """
    Lista libri con contatori coerenti (letto da disco se necessario).
    """
    items = _load_books_list()
    return [_coalesce_book_stats(b) for b in items if isinstance(b, dict)]


@router.post("/books/create", summary="Create Book")
def create_book(book: BookIn):
    items = _load_books_list()
    # id semplice
    safe = book.title.strip() or "Libro"
    slug = safe.lower().replace(" ", "-")
    suffix = datetime.utcnow().strftime("%H%M%S")  # riduci collisioni
    book_id = f"book_{slug}_{suffix}"

    # crea cartella capitoli
    _book_dir(book_id).mkdir(parents=True, exist_ok=True)

    meta = {
        "id": book_id,
        "title": book.title.strip() or "Senza titolo",
        "author": (book.author or "").strip(),
        "language": (book.language or "it").lower(),
        "chapters": book.chapters or [],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": "",
    }
    items.append(meta)
    _save_books_list(items)
    return {"ok": True, "book_id": book_id, **meta}


@router.delete("/books/{book_id}", summary="Delete Book", status_code=204)
def delete_book(book_id: str):
    items = _load_books_list()
    items = [b for b in items if (b.get("id") or "") != book_id]
    _save_books_list(items)

    # elimina cartella sul disco (capitoli)
    base = _book_dir(book_id)
    if base.exists():
        for p in base.glob("*"):
            try:
                p.unlink()
            except Exception:
                pass
        try:
            base.rmdir()
        except Exception:
            pass
    return


@router.get("/books/{book_id}/chapters/{chapter_id}", summary="Get Chapter")
def get_chapter(book_id: str, chapter_id: str):
    # prova API storage
    text = ""
    if hasattr(storage, "read_chapter_text"):
        try:
            text = storage.read_chapter_text(book_id, chapter_id) or ""
        except Exception:
            text = ""
    # fallback FS
    if not text:
        p = _chapter_path(book_id, chapter_id)
        if p.exists():
            try:
                text = p.read_text(encoding="utf-8")
            except Exception:
                text = ""
    if text == "":
        # non 404: può essere capitolo vuoto in editing
        return {"book_id": book_id, "chapter_id": chapter_id, "content": ""}

    return {"book_id": book_id, "chapter_id": chapter_id, "content": text}


@router.put("/books/{book_id}/chapters/{chapter_id}", summary="Upsert Chapter")
def upsert_chapter(book_id: str, chapter_id: str, body: ChapterUpdate):
    content = body.content or ""

    # scrivi via storage se c'è API
    ok = False
    if hasattr(storage, "write_chapter_text"):
        try:
            storage.write_chapter_text(book_id, chapter_id, content)
            ok = True
        except Exception:
            ok = False

    # fallback FS
    if not ok:
        base = _book_dir(book_id)
        base.mkdir(parents=True, exist_ok=True)
        p = base / f"{chapter_id}.md"
        p.write_text(content, encoding="utf-8")

    # aggiorna metadati libro (aggiungi capitolo se non presente)
    items = _load_books_list()
    for b in items:
        if (b.get("id") or "") == book_id:
            ch = b.get("chapters") or []
            if not any((c.get("id") == chapter_id) for c in ch if isinstance(c, dict)):
                ch.append({"id": chapter_id, "title": chapter_id})
                b["chapters"] = ch
            b["updated_at"] = datetime.utcnow().isoformat()
            break
    _save_books_list(items)

    return {"ok": True, "book_id": book_id, "chapter_id": chapter_id}


@router.delete("/books/{book_id}/chapters/{chapter_id}", summary="Delete Chapter", status_code=204)
def delete_chapter(book_id: str, chapter_id: str):
    # elimina file sul disco (.md e .txt)
    base = _book_dir(book_id)
    for p in [base / f"{chapter_id}.md", base / f"{chapter_id}.txt"]:
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    # aggiorna metadati
    items = _load_books_list()
    for b in items:
        if (b.get("id") or "") == book_id:
            ch = [c for c in (b.get("chapters") or []) if isinstance(c, dict) and c.get("id") != chapter_id]
            b["chapters"] = ch
            b["updated_at"] = datetime.utcnow().isoformat()
            break
    _save_books_list(items)
    return


# ---------------------- Export singolo capitolo ------------------- #

def _read_chapter_text(book_id: str, chapter_id: str) -> str:
    txt = ""
    if hasattr(storage, "read_chapter_text"):
        try:
            txt = storage.read_chapter_text(book_id, chapter_id) or ""
        except Exception:
            txt = ""
    if not txt:
        p = _chapter_path(book_id, chapter_id)
        if p.exists():
            try:
                txt = p.read_text(encoding="utf-8")
            except Exception:
                txt = ""
    return txt

@router.get(
    "/books/{book_id}/chapters/{chapter_id}.md",
    response_class=PlainTextResponse,
    summary="Export Chapter Md",
)
def export_chapter_md(book_id: str, chapter_id: str):
    return PlainTextResponse(_read_chapter_text(book_id, chapter_id))

@router.get(
    "/books/{book_id}/chapters/{chapter_id}.txt",
    response_class=PlainTextResponse,
    summary="Export Chapter Txt",
)
def export_chapter_txt(book_id: str, chapter_id: str):
    return PlainTextResponse(_read_chapter_text(book_id, chapter_id))

@router.get(
    "/books/{book_id}/chapters/{chapter_id}.pdf",
    summary="Export Chapter Pdf",
)
def export_chapter_pdf(book_id: str, chapter_id: str):
    txt = _read_chapter_text(book_id, chapter_id)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph(chapter_id, styles["Heading2"]), Spacer(1, 12)]
    for para in (txt or "").split("\n\n"):
        story.append(Paragraph(para.replace("\n", "<br/>"), styles["BodyText"]))
        story.append(Spacer(1, 6))
    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{chapter_id}.pdf"'})


# ---------------------- NUOVO: refresh metadati ------------------- #

@router.post("/books/refresh", summary="Rebuild library metadata from disk")
def refresh_books_from_disk():
    """
    Scansiona /chapters/*, ricostruisce l'elenco capitoli per ogni libro
    e salva i metadati aggiornati su disco.
    - Mantiene title/author/language esistenti quando possibile.
    - Se trova directory senza libro corrispondente, crea una voce base.
    """
    items = _load_books_list()
    by_id: Dict[str, Dict[str, Any]] = { (b.get("id") or ""): b for b in items if isinstance(b, dict) }

    # 1) directory presenti su disco
    root = storage.BASE_DIR / "chapters"
    root.mkdir(parents=True, exist_ok=True)
    for d in sorted([p for p in root.iterdir() if p.is_dir()]):
        book_id = d.name
        chapters = _scan_chapters_from_disk(book_id)
        b = by_id.get(book_id)
        if b is None:
            # libro non presente nei metadati -> crea scheda base
            b = {
                "id": book_id,
                "title": book_id.replace("_"," ").title(),
                "author": "",
                "language": "it",
                "chapters": chapters,
            }
            by_id[book_id] = b
        else:
            # aggiorna elenco capitoli mantenendo metadati esistenti
            b["chapters"] = chapters

        # aggiorna last updated
        b["updated_at"] = (
            max((c.get("updated_at") or "") for c in chapters) if chapters else ""
        )

    # 2) rimuovi dai metadati eventuali libri che non hanno più cartella
    existing_dirs = {p.name for p in root.iterdir() if p.is_dir()}
    for orphan in [bk for bk in list(by_id.values()) if (bk.get("id") or "") not in existing_dirs]:
        # li manteniamo, ma a capitoli vuoti; se vuoi, puoi eliminarli:
        # del by_id[orphan["id"]]
        orphan["chapters"] = orphan.get("chapters") or []
        orphan["updated_at"] = orphan.get("updated_at") or ""

    # 3) salva
    final_items = list(by_id.values())
    _save_books_list(final_items)

    # 4) restituisci sommario
    summary = []
    for b in final_items:
        enriched = _coalesce_book_stats(b)
        summary.append({
            "id": enriched["id"],
            "title": enriched.get("title") or "",
            "chapters_count": enriched.get("chapters_count", 0),
            "updated_at": enriched.get("updated_at") or "",
        })

    return {
        "ok": True,
        "books": summary,
        "count": len(summary),
        "root": root.as_posix(),
    }
