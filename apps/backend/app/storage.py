# apps/backend/app/storage.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_ROOT = "/opt/render/project/data/eccomibook"
BASE_DIR = Path(os.environ.get("STORAGE_ROOT", DEFAULT_ROOT)).resolve()

BOOKS_DIR = BASE_DIR / "books"
CHAPTERS_DIR = BASE_DIR / "chapters"
BOOKS_JSON = BASE_DIR / "books.json"

BOOKS_CACHE: Optional[List[Dict[str, Any]]] = None

def ensure_dirs() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    if not BOOKS_JSON.exists():
        BOOKS_JSON.write_text("[]", encoding="utf-8")

def load_books() -> List[Dict[str, Any]]:
    global BOOKS_CACHE
    if BOOKS_CACHE is not None:
        return BOOKS_CACHE
    ensure_dirs()
    try:
        data = json.loads(BOOKS_JSON.read_text(encoding="utf-8"))
        BOOKS_CACHE = data if isinstance(data, list) else []
    except Exception:
        BOOKS_CACHE = []
    return BOOKS_CACHE

def save_books(books: List[Dict[str, Any]]) -> None:
    global BOOKS_CACHE
    BOOKS_CACHE = books
    ensure_dirs()
    BOOKS_JSON.write_text(json.dumps(books, ensure_ascii=False, indent=2), encoding="utf-8")

def find_book(book_id: str) -> Optional[Dict[str, Any]]:
    for b in load_books():
        if b.get("id") == book_id:
            return b
    return None

def persist_book(book: Dict[str, Any]) -> None:
    books = load_books()
    for i, b in enumerate(books):
        if b.get("id") == book.get("id"):
            books[i] = book
            save_books(books)
            return
    books.append(book)
    save_books(books)

def reorder_chapters(book_id: str, ordered_ids: List[str]) -> Dict[str, Any]:
    book = find_book(book_id)
    if not book:
        raise ValueError("Libro non trovato")
    chapters = book.get("chapters", [])
    by_id = {c["id"]: c for c in chapters if "id" in c}
    new_list = []
    seen = set()
    for cid in ordered_ids:
        if cid in by_id and cid not in seen:
            new_list.append(by_id[cid]); seen.add(cid)
    for c in chapters:
        cid = c.get("id")
        if cid and cid not in seen:
            new_list.append(c); seen.add(cid)
    book["chapters"] = new_list
    persist_book(book)
    return book
