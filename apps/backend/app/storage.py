# apps/backend/app/storage.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Tuple

# Directory base scrivibile:
# - default: /tmp/eccomibook (sempre scrivibile su Render)
# - puoi sovrascrivere mettendo STORAGE_DIR nelle env vars di Render
BASE_DIR = Path(os.getenv("STORAGE_DIR", "/tmp/eccomibook")).resolve()

BOOKS_DIR   = BASE_DIR / "books"
EXPORTS_DIR = BASE_DIR / "exports"

def ensure_dirs() -> None:
    """Crea le cartelle necessarie se non esistono (no error se già esistono)."""
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

def book_json_path(book_id: str) -> Path:
    """Percorso dove potresti salvare eventuale JSON del libro (se/quando servirà)."""
    return BOOKS_DIR / f"{book_id}.json"

def export_pdf_path(book_id: str) -> Path:
    """Percorso del PDF esportato."""
    return EXPORTS_DIR / f"{book_id}.pdf"

def exports_dir_and_filename(book_id: str, ext: str) -> Tuple[Path, str]:
    """Percorso file di export e nome file (per download)."""
    filename = f"{book_id}.{ext}"
    return (EXPORTS_DIR / filename, filename)
