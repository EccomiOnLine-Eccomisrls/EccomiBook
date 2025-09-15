import os
from pathlib import Path
from .settings import get_settings

# Directory base (robusta su Render)
DEFAULT_DIRS = [
    # 1) env var esplicita
    lambda s: Path(s.storage_dir) if s.storage_dir else None,
    # 2) ./data nella root di esecuzione
    lambda s: Path("./data"),
    # 3) /tmp fallback sempre scrivibile
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
            test = p / ".touch"
            test.write_text("ok")
            test.unlink(missing_ok=True)
            return p
        except Exception:
            continue
    # estremo fallback
    return Path("/tmp")


BASE_DIR = _pick_dir()


def ensure_dirs() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)


def file_path(filename: str) -> Path:
    return BASE_DIR / filename


def public_url(filename: str) -> str:
    # URL di download esposto dalla stessa app
    return f"/downloads/{filename}"
