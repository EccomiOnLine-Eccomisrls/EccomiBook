from __future__ import annotations

from fastapi import APIRouter, HTTPException, Header, Path as FPath, UploadFile, File
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path as FSPath
from random import randint
import io, zipfile, os

from app import storage

router = APIRouter()

# ---------------- Pydantic ----------------
class BookIn(BaseModel):
    title: str
    author: str | None = None
    abstract: str | None = None
    description: str | None = None
    genre: str | None = None
    language: str = "it"
    plan: str | None = None
    chapters: List[Dict[str, Any]] = []

class BookUpdateIn(BaseModel):
    title: str | None = None
    author: str | None = None
    abstract: str | None = None
    description: str | None = None
    genre: str | None = None
    language: str | None = None
    plan: str | None = None

class ChapterUpdate(BaseModel):
    content: str

class ReorderIn(BaseModel):
    order: List[str]  # lista di chapter_id, nell’ordine desiderato

# --------------- Helpers ------------------
SCHEMA_VERSION = 1

def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def _book_index() -> List[Dict[str, Any]]:
    books = getattr(storage, "BOOKS_CACHE", None)
    if books is None:
        books = storage.load_books_from_disk()
        storage.BOOKS_CACHE = books
    return books

def _save_index(books: List[Dict[str, Any]]) -> None:
    storage.save_books_to_disk(books)
    storage.BOOKS_CACHE = books

def _ensure_book_folder(book_id: str) -> FSPath:
    folder = storage.CHAPTERS_DIR / book_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder

def _find_book(books: List[Dict[str, Any]], book_id: str) -> Dict[str, Any] | None:
    return next((b for b in books if (b.get("id") or b.get("book_id")) == book_id), None)

def _check_admin_key(x_api_key: str | None):
    expected = os.getenv("BACKUP_API_KEY", "").strip()
    if expected and (x_api_key or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ---------------- MIGRAZIONE SCHEMA ----------------
def _ensure_schema():
    books = _book_index()
    changed = False
    for b in books:
        if "schema_version" not in b:
            b["schema_version"] = SCHEMA_VERSION
            changed = True
    if changed:
        _save_index(books)

# --------------- API: LIBRI ----------------------
@router.get("/books", summary="List Books")
def list_books():
    _ensure_schema()
    return _book_index()

@router.post("/books/create", summary="Create Book")
def create_book(data: BookIn):
    safe_title = data.title.lower().strip().replace(" ", "-").replace("/", "-")
    book_id = f"book_{safe_title}_{datetime.utcnow().strftime('%H%M%S')}{randint(1000,9999)}"
    book = {
        "id": book_id,
        "title": data.title,
        "author": (data.author or ""),
        "language": (data.language or "it"),
        "abstract": (data.abstract or ""),
        "description": (data.description or ""),
        "genre": (data.genre or ""),
        "plan": (data.plan or ""),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "schema_version": SCHEMA_VERSION,
        "chapters": [],  # l’ordine in questa lista È l’ordine mostrato
    }
    _ensure_book_folder(book_id)
    books = _book_index()
    books.append(book)
    _save_index(books)
    try: storage.snapshot_zip(max_keep=20)
    except: pass
    return {"ok": True, "book_id": book_id, "title": book["title"]}

@router.put("/books/{book_id}", summary="Update Book (title/author/language/…)")
def update_book(book_id: str, data: BookUpdateIn, x_api_key: str | None = Header(default=None)):
    books = _book_index()
    b = _find_book(books, book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    if data.title is not None:       b["title"] = data.title
    if data.author is not None:      b["author"] = data.author
    if data.language is not None:    b["language"] = (data.language or "it")
    if data.abstract is not None:    b["abstract"] = data.abstract
    if data.description is not None: b["description"] = data.description
    if data.genre is not None:       b["genre"] = data.genre
    if data.plan is not None:        b["plan"] = data.plan

    b["updated_at"] = _now_iso()
    _save_index(books)
    try: storage.snapshot_zip(max_keep=20)
    except: pass
    return {"ok": True, "book": b}

@router.delete("/books/{book_id}", status_code=204, summary="Delete Book")
def delete_book(book_id: str):
    books = _book_index()
    books = [b for b in books if (b.get("id") or b.get("book_id")) != book_id]
    _save_index(books)
    folder = storage.CHAPTERS_DIR / book_id
    if folder.exists():
        for p in folder.glob("*"):
            try: p.unlink()
            except Exception: pass
        try: folder.rmdir()
        except Exception: pass
    try: storage.snapshot_zip(max_keep=20)
    except: pass
    return

# --------------- API: CAPITOLI ----------------------
# EXPORT capitolo
@router.get("/books/{book_id}/chapters/{chapter_id}.md",
            response_class=PlainTextResponse, summary="Export Chapter Md")
def export_chapter_md(book_id: str, chapter_id: str):
    text = storage.read_chapter_text(book_id, chapter_id)
    return PlainTextResponse(text, media_type="text/markdown; charset=utf-8")

@router.get("/books/{book_id}/chapters/{chapter_id}.txt",
            response_class=PlainTextResponse, summary="Export Chapter Txt")
def export_chapter_txt(book_id: str, chapter_id: str):
    text = storage.read_chapter_text(book_id, chapter_id)
    return PlainTextResponse(text, media_type="text/plain; charset=utf-8")

@router.get("/books/{book_id}/chapters/{chapter_id}.pdf", summary="Export Chapter Pdf")
def export_chapter_pdf(book_id: str, chapter_id: str):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    text = storage.read_chapter_text(book_id, chapter_id)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=f"{book_id} - {chapter_id}")
    styles = getSampleStyleSheet()
    story = [Paragraph(f"{chapter_id}", styles["Heading2"]), Spacer(1, 12)]
    for para in (text or "").split("\n\n"):
        story.append(Paragraph(para.replace("\n", "<br/>"), styles["BodyText"]))
        story.append(Spacer(1, 6))
    doc.build(story)
    pdf = buf.getvalue(); buf.close()
    headers = {"Content-Disposition": f'attachment; filename="{chapter_id}.pdf"'}
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf", headers=headers)

@router.get("/books/{book_id}/chapters/{chapter_id}", summary="Get Chapter")
def get_chapter(book_id: str, chapter_id: str = FPath(..., pattern=r"[^.]+$")):
    text = storage.read_chapter_text(book_id, chapter_id)
    return {"book_id": book_id, "chapter_id": chapter_id, "content": text}

@router.put("/books/{book_id}/chapters/{chapter_id}", summary="Upsert Chapter")
def upsert_chapter(book_id: str, chapter_id: str, data: ChapterUpdate):
    storage.write_chapter_text(book_id, chapter_id, data.content or "")
    books = _book_index()
    b = _find_book(books, book_id)
    if not b:
        b = {
            "id": book_id, "title": book_id, "author": "", "language": "it",
            "created_at": _now_iso(), "updated_at": _now_iso(),
            "schema_version": SCHEMA_VERSION, "chapters": [],
        }
        books.append(b)

    ch = b.get("chapters") or []
    found = next((c for c in ch if (c.get("id") or c.get("chapter_id")) == chapter_id), None)
    if not found:
        ch.append({"id": chapter_id, "title": chapter_id, "updated_at": _now_iso()})
        b["chapters"] = ch
    else:
        found["updated_at"] = _now_iso()

    b["updated_at"] = _now_iso()
    _save_index(books)
    try: storage.snapshot_zip(max_keep=20)
    except: pass
    return {"ok": True, "book_id": book_id, "chapter_id": chapter_id}

@router.delete("/books/{book_id}/chapters/{chapter_id}", status_code=204, summary="Delete Chapter")
def delete_chapter(book_id: str, chapter_id: str):
    storage.delete_chapter_files(book_id, chapter_id)
    books = _book_index()
    b = _find_book(books, book_id)
    if b:
        ch = b.get("chapters") or []
        ch = [c for c in ch if (c.get("id") or c.get("chapter_id")) != chapter_id]
        b["chapters"] = ch
        b["updated_at"] = _now_iso()
        _save_index(books)
    try: storage.snapshot_zip(max_keep=20)
    except: pass
    return

# --------- Reorder capitoli (NUOVO) ----------
@router.put("/books/{book_id}/chapters/reorder", summary="Reorder chapters by list of IDs")
def reorder_chapters(book_id: str, data: ReorderIn):
    books = _book_index()
    b = _find_book(books, book_id)
    if not b:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    existing = b.get("chapters") or []
    by_id = { (c.get("id") or c.get("chapter_id")): c for c in existing }

    # Mantieni solo gli ID validi e nell’ordine dato
    new_list: List[Dict[str, Any]] = []
    seen = set()
    for cid in data.order:
        c = by_id.get(cid)
        if c and cid not in seen:
            new_list.append(c); seen.add(cid)

    # Aggiungi eventuali capitoli non menzionati (in coda, ordine attuale)
    for c in existing:
        cid = c.get("id") or c.get("chapter_id")
        if cid not in seen:
            new_list.append(c); seen.add(cid)

    b["chapters"] = new_list
    b["updated_at"] = _now_iso()
    _save_index(books)
    try: storage.snapshot_zip(max_keep=20)
    except: pass
    return {"ok": True, "count": len(new_list), "book_id": book_id}

# --------- Rebuild libreria da DISCO ---------
@router.post("/books/refresh", summary="Rebuild library metadata from disk")
def books_refresh():
    root = storage.CHAPTERS_DIR
    books: List[Dict[str, Any]] = []
    if root.exists():
        for book_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
            book_id = book_dir.name
            chapters: List[Dict[str, Any]] = []
            last_update: str | None = None
            for f in sorted(book_dir.glob("*.md")):
                cid = f.stem
                ts = datetime.utcfromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds") + "Z"
                chapters.append({"id": cid, "title": cid, "updated_at": ts})
                last_update = ts
            for f in sorted(book_dir.glob("*.txt")):
                cid = f.stem
                if not any(c["id"] == cid for c in chapters):
                    ts = datetime.utcfromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds") + "Z"
                    chapters.append({"id": cid, "title": cid, "updated_at": ts})
                    last_update = ts
            books.append({
                "id": book_id, "title": book_id, "author": "", "language": "it",
                "created_at": last_update or _now_iso(),
                "updated_at": last_update or _now_iso(),
                "schema_version": SCHEMA_VERSION,
                "chapters": chapters,
            })
    _save_index(books)
    try: storage.snapshot_zip(max_keep=20)
    except: pass
    return {"ok": True, "books": len(books)}

# =================== BACKUP / RESTORE ======================
@router.get("/admin/backup", summary="Create and download a ZIP backup")
def admin_backup(x_api_key: str | None = Header(default=None)):
    _check_admin_key(x_api_key)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        index_bytes = storage.books_index_bytes()
        zf.writestr("books_index.json", index_bytes)
        root = storage.CHAPTERS_DIR
        if root.exists():
            for p in root.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(root.parent))
    buf.seek(0)
    filename = f"eccomibook_backup_{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.zip"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(buf, media_type="application/zip", headers=headers)

@router.post("/admin/restore", summary="Restore from a ZIP backup")
def admin_restore(file: UploadFile = File(...), x_api_key: str | None = Header(default=None)):
    _check_admin_key(x_api_key)
    data = file.file.read()
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        if "books_index.json" in zf.namelist():
            storage.save_books_index_bytes(zf.read("books_index.json"))
        root = storage.CHAPTERS_DIR
        root.mkdir(parents=True, exist_ok=True)
        for name in zf.namelist():
            if name.startswith("chapters/") and not name.endswith("/"):
                dest = root.parent / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(zf.read(name))
    storage.BOOKS_CACHE = storage.load_books_from_disk()
    return {"ok": True, "restored": True}
