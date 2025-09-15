from __future__ import annotations
import time, uuid
from datetime import date
from typing import Dict, List, Optional
from .models import BookCreate, BookOut, ChapterCreate, ChapterOut, Plan

# ---------------- In-memory ----------------
_DB_BOOKS: Dict[str, BookOut] = {}
# usage counters
_USAGE_BOOKS_MONTH: Dict[str, Dict[str, int]] = {}      # user_id -> { "YYYY-MM": count }
_USAGE_CHAPTERS_DAY: Dict[str, Dict[str, int]] = {}     # user_id -> { "YYYY-MM-DD": count }

def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

# -------------- Usage helpers --------------
def get_usage_books_month(user_id: str, month: str) -> int:
    return _USAGE_BOOKS_MONTH.get(user_id, {}).get(month, 0)

def get_usage_chapters_day(user_id: str, day: str) -> int:
    return _USAGE_CHAPTERS_DAY.get(user_id, {}).get(day, 0)

def inc_book(user_id: str):
    m = date.today().strftime("%Y-%m")
    _USAGE_BOOKS_MONTH.setdefault(user_id, {})
    _USAGE_BOOKS_MONTH[user_id][m] = _USAGE_BOOKS_MONTH[user_id].get(m, 0) + 1

def inc_chapter(user_id: str):
    d = date.today().isoformat()
    _USAGE_CHAPTERS_DAY.setdefault(user_id, {})
    _USAGE_CHAPTERS_DAY[user_id][d] = _USAGE_CHAPTERS_DAY[user_id].get(d, 0) + 1

# -------------- Books CRUD -----------------
def list_books() -> List[BookOut]:
    return list(_DB_BOOKS.values())

def create_book(body: BookCreate, plan: Plan = Plan.GROWTH) -> BookOut:
    book_id = _gen_id("book")
    book = BookOut(id=book_id, plan=plan, **body.model_dump(), chapters=[])
    _DB_BOOKS[book_id] = book
    return book

def get_book(book_id: str) -> Optional[BookOut]:
    return _DB_BOOKS.get(book_id)

# -------------- Chapters -------------------
def add_chapter(book_id: str, body: ChapterCreate) -> ChapterOut:
    book = get_book(book_id)
    if not book:
        return None
    ch = ChapterOut(id=_gen_id("ch"), **body.model_dump())
    book.chapters.append(ch)
    return ch

def update_chapter(book_id: str, chapter_id: str, body: ChapterCreate) -> Optional[ChapterOut]:
    book = get_book(book_id)
    if not book:
        return None
    for i, ch in enumerate(book.chapters):
        if ch.id == chapter_id:
            new_ch = ChapterOut(id=ch.id, **body.model_dump())
            book.chapters[i] = new_ch
            return new_ch
    return None

# -------------- AI / Export stubs ----------
def generate_chapter_stub(body: ChapterCreate) -> ChapterCreate:
    """
    Qui andrà la chiamata al tuo modello AI.
    Per ora ritorniamo il body così com’è (placeholder).
    """
    return body

def export_book_stub(book_id: str, format: str = "pdf") -> dict:
    """
    Stub export: restituisce metadati + un fake URL (che potrai sostituire con
    un vero link a storage S3/Cloud/etc o StreamingResponse).
    """
    book = get_book(book_id)
    if not book:
        return {"ok": False, "error": "book_not_found"}

    fname = f"{book_id}.{format}"
    url = f"https://example.com/downloads/{fname}"  # placeholder
    return {
        "ok": True,
        "book_id": book_id,
        "format": format,
        "file_name": fname,
        "url": url,
        "chapters": len(book.chapters),
        "generated_at": int(time.time()),
    }
