import os
from pathlib import Path
from typing import Union
from .settings import get_settings

# Scelta root: preferisci settings.storage_dir (es. /var/data su Render)
DEFAULT_DIRS = [
    lambda s: Path(s.storage_dir) if getattr(s, "storage_dir", None) else None,
    lambda s: Path("./data"),
    lambda s: Path("/tmp/eccomibook-data"),
]

def _pick_dir() -> Path:
    s = get_settings()
    for maker in DEFAULT_DIRS:
        p = maker(s)
        if p is None:
            continue
        try:
            p.mkdir(parents=True, exist_ok=True)
            t = p / ".touch"
            t.write_text("ok")
            t.unlink(missing_ok=True)
            return p
        except Exception:
            continue
    return Path("/tmp")

# Root effettiva (es. /var/data in produzione, ./data in locale)
BASE_DIR = _pick_dir()

def ensure_dirs() -> None:
    (BASE_DIR / "chapters").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "books").mkdir(parents=True, exist_ok=True)

def file_path(relpath: Union[str, Path]) -> Path:
    """
    Accetta percorsi con sottocartelle, es.:
    - "chapters/ch_abc.pdf"
    - "books/bk_123.pdf"
    """
    p = (BASE_DIR / str(relpath)).resolve()
    if not str(p).startswith(str(BASE_DIR.resolve())):
        raise ValueError("Percorso non valido")
    return p

def public_url(relpath: Union[str, Path]) -> str:
    """URL di download servito dalla stessa app, compatibile con /downloads/{subpath:path}."""
    return f"/downloads/{relpath}"
