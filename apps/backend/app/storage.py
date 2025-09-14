import json, os, uuid, shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from app.models import Book, Chapter
from app.settings import settings

DATA_DIR = Path(settings.DATA_DIR)
BOOKS_JSON = DATA_DIR / "books.json"

def _now():
    return datetime.utcnow()

def _ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def _load_all() -> List[Book]:
    _ensure_dirs()
    if not BOOKS_JSON.exists():
        return []
    with open(BOOKS_JSON, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [Book(**b) for b in raw]

def _save_all(books: List[Book]) -> None:
    _ensure_dirs()
    with open(BOOKS_JSON, "w", encoding="utf-8") as f:
        json.dump([b.model_dump() for b in books], f, ensure_ascii=False, indent=2, default=str)

# -------- Public API --------

def list_books() -> List[Book]:
    return _load_all()

def get_book(book_id: str) -> Optional[Book]:
    for b in _load_all():
        if b.id == book_id:
            return b
    return None

def create_book(title: str, genre: str, language: str, plan: str | None) -> Book:
    books = _load_all()
    b = Book(
        id=str(uuid.uuid4()), title=title, genre=genre, language=language,
        plan=plan or "owner_full", outline=[], chapters=[],
        created_at=_now(), updated_at=_now()
    )
    books.append(b)
    _save_all(books)
    return b

def save_book(book: Book) -> None:
    books = _load_all()
    for i, b in enumerate(books):
        if b.id == book.id:
            books[i] = book
            _save_all(books)
            return
    books.append(book)
    _save_all(books)

def add_chapter(book_id: str, title: str, content_md: str, images: list[str]) -> Chapter:
    book = get_book(book_id)
    if not book:
        raise FileNotFoundError("book not found")
    ch = Chapter(
        id=str(uuid.uuid4()),
        index=len(book.chapters),
        title=title,
        content_md=content_md,
        images=images,
        created_at=_now(), updated_at=_now()
    )
    book.chapters.append(ch)
    book.updated_at = _now()
    save_book(book)
    return ch

def update_chapter(book_id: str, chapter_id: str, title: str | None, content_md: str | None) -> Chapter:
    book = get_book(book_id)
    if not book:
        raise FileNotFoundError("book not found")
    for ch in book.chapters:
        if ch.id == chapter_id:
            if title is not None: ch.title = title
            if content_md is not None: ch.content_md = content_md
            ch.updated_at = _now()
            book.updated_at = _now()
            save_book(book)
            return ch
    raise FileNotFoundError("chapter not found")

def export_book_mdzip(book: Book) -> str:
    """Crea zip con capitoli markdown. Ritorna path file."""
    _ensure_dirs()
    tmp_dir = DATA_DIR / f"export_{book.id}"
    out_zip = DATA_DIR / f"{book.id}.zip"
    if tmp_dir.exists(): shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # front matter
    with open(tmp_dir / "00_info.md", "w", encoding="utf-8") as f:
        f.write(f"# {book.title}\n\nGenere: {book.genre}\nLingua: {book.language}\n\n")

    for ch in book.chapters:
        fname = f"{ch.index:02d}_{(ch.title or 'chapter').strip().replace(' ', '_')}.md"
        with open(tmp_dir / fname, "w", encoding="utf-8") as f:
            f.write(f"# {ch.title}\n\n{ch.content_md}\n")

    if out_zip.exists(): out_zip.unlink()
    shutil.make_archive(str(out_zip.with_suffix("")), "zip", tmp_dir)
    shutil.rmtree(tmp_dir)
    return str(out_zip)

def export_book_json(book: Book) -> str:
    _ensure_dirs()
    out = DATA_DIR / f"{book.id}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(book.model_dump(), f, ensure_ascii=False, indent=2, default=str)
    return str(out)
