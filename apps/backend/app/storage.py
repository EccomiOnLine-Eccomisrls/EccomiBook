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
    """Ritorna un Path dentro BASE_DIR (compat per altri moduli)."""
    ensure_dirs()
    return (BASE_DIR / rel).resolve()

# ---- Persistenza libri -------------------------------------------------
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

# ---- File capitoli -----------------------------------------------------
def _chapter_path(book_id: str, chapter_id: str) -> Path:
    """Percorso assoluto del file capitolo."""
    ensure_dirs()
    folder = BASE_DIR / "chapters" / book_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{chapter_id}.md"

def save_chapter_file(book_id: str, chapter_id: str, content: str) -> str:
    """Scrive il contenuto e ritorna il percorso relativo da salvare nel libro."""
    path = _chapter_path(book_id, chapter_id)
    path.write_text(content or "", encoding="utf-8")
    return path.relative_to(BASE_DIR).as_posix()

def read_chapter_file(book_id: str, chapter_id: str) -> str:
    """Legge il contenuto del capitolo (eccezione se non trovato)."""
    path = _chapter_path(book_id, chapter_id)
    if not path.exists():
        raise FileNotFoundError
    return path.read_text(encoding="utf-8")
