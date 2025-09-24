# apps/backend/app/storage.py
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, List, Dict

# Root persistente su Render: /opt/render/project/data/...
# Puoi override con env STORAGE_ROOT
DEFAULT_ROOT = "/opt/render/project/data/eccomibook"
BASE_DIR = Path(os.environ.get("STORAGE_ROOT", DEFAULT_ROOT)).resolve()

BOOKS_DIR = BASE_DIR / "books"
CHAPTERS_DIR = BASE_DIR / "chapters"
BOOKS_JSON = BASE_DIR / "books.json"

# Cache opzionale in-process (usata dai router)
BOOKS_CACHE: List[Dict[str, Any]] | None = None


def ensure_dirs() -> None:
    """
    Crea le cartelle richieste e inizializza books.json se mancante.
    """
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    if not BOOKS_JSON.exists():
        # inizializza un indice vuoto
        try:
            BOOKS_JSON.write_text("[]", encoding="utf-8")
        except Exception as e:
            print(f"⚠️  Impossibile creare {BOOKS_JSON}: {e}")


def load_books_from_disk() -> List[Dict[str, Any]]:
    """
    Legge books.json. Se non esiste o non è valido, ritorna [] e prova a riparare.
    """
    ensure_dirs()
    try:
        raw = BOOKS_JSON.read_text(encoding="utf-8")
        data = json.loads(raw or "[]")
        if not isinstance(data, list):
            raise ValueError("books.json non è una lista")
        return data
    except FileNotFoundError:
        # ripara creando un file vuoto
        try:
            BOOKS_JSON.write_text("[]", encoding="utf-8")
        except Exception as e:
            print(f"⚠️  Impossibile creare {BOOKS_JSON}: {e}")
        return []
    except Exception as e:
        # file corrotto → backup e reset
        try:
            backup = BOOKS_JSON.with_suffix(".json.bak")
            shutil.copyfile(BOOKS_JSON, backup)
            print(f"⚠️  {BOOKS_JSON} corrotto. Backup in {backup}. Reinizializzo.")
        except Exception:
            pass
        try:
            BOOKS_JSON.write_text("[]", encoding="utf-8")
        except Exception as e2:
            print(f"⚠️  Impossibile riscrivere {BOOKS_JSON}: {e2}")
        return []


def save_books_to_disk(books: List[Dict[str, Any]]) -> None:
    """
    Salvataggio atomico (scrive su .tmp e fa replace). 
    """
    ensure_dirs()
    tmp = BOOKS_JSON.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(books, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, BOOKS_JSON)
    except Exception as e:
        print(f"⚠️  Errore salvataggio {BOOKS_JSON}: {e}")
        # tenta a fallback diretto
        try:
            BOOKS_JSON.write_text(json.dumps(books, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e2:
            print(f"⚠️  Fallback fallito su {BOOKS_JSON}: {e2}")


# ------------- Utility opzionali usate dagli endpoint -------------

def read_chapter_text(book_id: str, chapter_id: str) -> str:
    """
    Ritorna il contenuto di un capitolo (.md o .txt).
    """
    base = CHAPTERS_DIR / book_id
    for ext in (".md", ".txt"):
        p = base / f"{chapter_id}{ext}"
        if p.exists():
            try:
                return p.read_text(encoding="utf-8")
            except Exception:
                return ""
    return ""


def write_chapter_text(book_id: str, chapter_id: str, text: str) -> Path:
    """
    Scrive/aggiorna un capitolo .md.
    """
    folder = CHAPTERS_DIR / book_id
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / f"{chapter_id}.md"
    p.write_text(text or "", encoding="utf-8")
    return p


def delete_chapter_files(book_id: str, chapter_id: str) -> None:
    """
    Elimina i file del capitolo (.md/.txt). Cancella cartella se vuota.
    """
    folder = CHAPTERS_DIR / book_id
    for ext in (".md", ".txt"):
        p = folder / f"{chapter_id}{ext}"
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
    try:
        if folder.exists() and not any(folder.iterdir()):
            folder.rmdir()
    except Exception:
        pass
