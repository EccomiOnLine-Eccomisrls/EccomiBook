# apps/backend/app/storage.py
from __future__ import annotations
from pathlib import Path
from typing import Any
import json

# Radice dello storage persistente su Render
BASE_DIR = Path("/opt/render/project/data/eccomibook")

# ----------------------------- cartelle base -----------------------------

def ensure_dirs() -> None:
    """Crea le cartelle necessarie sul disco persistente."""
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "chapters").mkdir(exist_ok=True)  # capitoli (per libro)
    (BASE_DIR / "books").mkdir(exist_ok=True)     # esport PDF/libri
    (BASE_DIR / "admin").mkdir(exist_ok=True)     # es. users.json

def file_path(rel: str) -> Path:
    """
    Ritorna un Path dentro BASE_DIR per compatibilità con altri moduli
    (es. users.py fa storage.file_path("admin/users.json")).
    """
    ensure_dirs()
    return (BASE_DIR / rel).resolve()

# ----------------------------- util JSON --------------------------------

def read_json(path: Path) -> Any:
    """Legge JSON, ritorna None in caso di errore/assenza."""
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None

def write_json(path: Path, data: Any) -> None:
    """Scrive JSON in modo atomico."""
    ensure_dirs()
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)

# ----------------------------- “DB” libri --------------------------------

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
        # Log minimale in MVP
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

# ----------------------------- capitoli ----------------------------------

def _chapter_path(book_id: str, chapter_id: str) -> Path:
    """
    Percorso assoluto del file capitolo.
    Es: /data/eccomibook/chapters/<book_id>/<chapter_id>.md
    """
    ensure_dirs()
    folder = BASE_DIR / "chapters" / book_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{chapter_id}.md"

def save_chapter_file(book_id: str, chapter_id: str, content: str) -> str:
    """
    Salva il contenuto del capitolo su disco e ritorna il percorso RELATIVO
    (es. 'chapters/<book_id>/<chapter_id>.md') da memorizzare nel libro.
    """
    path = _chapter_path(book_id, chapter_id)
    path.write_text(content or "", encoding="utf-8")
    return path.relative_to(BASE_DIR).as_posix()

def read_chapter_file(book_id: str, chapter_id: str) -> str:
    """Legge il contenuto di un capitolo; ritorna stringa vuota se non esiste."""
    path = _chapter_path(book_id, chapter_id)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""

# ----------------------------- export libri ------------------------------

def exported_book_pdf_path(book_id: str) -> Path:
    """
    Percorso suggerito per un PDF esportato del libro.
    Es: /data/eccomibook/books/<book_id>.pdf
    """
    ensure_dirs()
    return (BASE_DIR / "books" / f"{book_id}.pdf")
