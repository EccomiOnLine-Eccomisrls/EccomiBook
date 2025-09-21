# apps/backend/app/storage.py
from __future__ import annotations
from pathlib import Path
import json

# PDF
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

# Radice storage persistente
BASE_DIR = Path("/opt/render/project/data/eccomibook")

def ensure_dirs() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "chapters").mkdir(exist_ok=True)
    (BASE_DIR / "books").mkdir(exist_ok=True)
    (BASE_DIR / "admin").mkdir(exist_ok=True)

def file_path(rel: str) -> Path:
    ensure_dirs()
    return (BASE_DIR / rel).resolve()

# ── Persistenza libri ───────────────────────────────────
BOOKS_FILE = BASE_DIR / "books.json"

def load_books_from_disk() -> dict:
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
    ensure_dirs()
    try:
        tmp = BOOKS_FILE.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(books or {}, f, ensure_ascii=False, indent=2)
        tmp.replace(BOOKS_FILE)
    except Exception:
        print("⚠️  Impossibile salvare books.json")

# ── File capitoli ───────────────────────────────────────
def chapter_path(book_id: str, chapter_id: str) -> Path:
    ensure_dirs()
    folder = BASE_DIR / "chapters" / book_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{chapter_id}.md"

def save_chapter_file(book_id: str, chapter_id: str, content: str) -> str:
    p = chapter_path(book_id, chapter_id)
    p.write_text(content or "", encoding="utf-8")
    return p.relative_to(BASE_DIR).as_posix()

def read_chapter_file(book_id: str, chapter_id: str) -> tuple[bool, str, str]:
    p = chapter_path(book_id, chapter_id)
    rel = p.relative_to(BASE_DIR).as_posix()
    if not p.exists():
        return False, "", rel
    try:
        txt = p.read_text(encoding="utf-8")
    except Exception:
        txt = ""
    return True, txt, rel

# ── Export PDF ───────────────────────────────────────────
def make_chapter_pdf(book_id: str, chapter_id: str, content: str) -> Path:
    """
    Crea un PDF semplice dal contenuto del capitolo e ritorna il Path del PDF.
    """
    folder = BASE_DIR / "chapters" / book_id
    folder.mkdir(parents=True, exist_ok=True)
    pdf_path = folder / f"{chapter_id}.pdf"

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4
    x = 2 * cm
    y = height - 2 * cm

    title = f"{chapter_id} — {book_id}"
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, title)
    y -= 1 * cm

    c.setFont("Helvetica", 10)
    for line in (content or "").splitlines() or [""]:
        if y < 2 * cm:
            c.showPage()
            y = height - 2 * cm
            c.setFont("Helvetica", 10)
        c.drawString(x, y, line[:95])
        y -= 14
    c.save()
    return pdf_path
