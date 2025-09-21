# apps/backend/app/storage.py
from __future__ import annotations
from pathlib import Path
import json

# Radice dello storage persistente su Render
BASE_DIR = Path("/opt/render/project/data/eccomibook")

def ensure_dirs() -> None:
    """Crea le cartelle necessarie sul disco persistente."""
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "chapters").mkdir(exist_ok=True)
    (BASE_DIR / "books").mkdir(exist_ok=True)
    (BASE_DIR / "admin").mkdir(exist_ok=True)   # per users.json, ecc.

def file_path(rel: str) -> Path:
    """Path dentro BASE_DIR (compat per altri moduli)."""
    ensure_dirs()
    return (BASE_DIR / rel).resolve()

# ── Persistenza libri ────────────────────────────────────────────────────────

BOOKS_FILE = BASE_DIR / "books.json"

def load_books_from_disk() -> dict:
    """Carica il 'DB' libri (dict) da disco; se non esiste ritorna {}."""
    ensure_dirs()
    try:
        if BOOKS_FILE.exists():
            with BOOKS_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return dict(data or {})
    except Exception:
        print("⚠️  Impossibile leggere books.json (uso DB vuoto)")
    return {}

def save_books_to_disk(books: dict) -> None:
    """Salva il 'DB' libri su disco in modo atomico."""
    ensure_dirs()
    try:
        tmp = BOOKS_FILE.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(books or {}, f, ensure_ascii=False, indent=2)
        tmp.replace(BOOKS_FILE)
    except Exception:
        print("⚠️  Impossibile salvare books.json")

# ── File capitoli ────────────────────────────────────────────────────────────

def chapter_path(book_id: str, chapter_id: str) -> Path:
    """
    Percorso ASSOLUTO del file capitolo.
    Es: /data/eccomibook/chapters/<book_id>/<chapter_id>.md
    """
    ensure_dirs()
    folder = BASE_DIR / "chapters" / book_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{chapter_id}.md"

def save_chapter_file(book_id: str, chapter_id: str, content: str) -> str:
    """
    Salva il contenuto su disco e ritorna il PERCORSO RELATIVO
    (es. 'chapters/<book_id>/<chapter_id>.md').
    """
    p = chapter_path(book_id, chapter_id)
    p.write_text(content or "", encoding="utf-8")
    return p.relative_to(BASE_DIR).as_posix()

def read_chapter_file(book_id: str, chapter_id: str) -> tuple[bool, str, str]:
    """
    Legge il capitolo da disco.
    Ritorna (exists, content, rel_path).
    """
    p = chapter_path(book_id, chapter_id)
    rel = p.relative_to(BASE_DIR).as_posix()
    if not p.exists():
        return False, "", rel
    try:
        txt = p.read_text(encoding="utf-8")
    except Exception:
        txt = ""
    return True, txt, rel

def delete_chapter_file(book_id: str, chapter_id: str) -> bool:
    p = chapter_path(book_id, chapter_id)
    if p.exists():
        try:
            p.unlink()
            return True
        except Exception:
            return False
    return False
