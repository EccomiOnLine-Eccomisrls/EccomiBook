# apps/backend/app/main.py
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Header, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import os
import time
import uuid

# (a) import storage (usa /tmp/eccomibook come base) 
from app import storage

# --- PDF utilities (ReportLab) ---
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

APP_NAME = os.getenv("APP_NAME", "EccomiBook Backend")
APP_ENV = os.getenv("APP_ENV", "production")
OWNER_API_KEY = os.getenv("OWNER_API_KEY", "owner_full_key")  # chiave "tutto aperto"

app = FastAPI(title=APP_NAME, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restringi in prod se vuoi
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- In-memory storage (MVP) ----------------
# Nota: va bene per demo; per persistenza reale useremo un DB più avanti.
BOOKS: Dict[str, Dict] = {}  # book_id -> {"id", "title","author","language","genre","plan","chapters":[...]}

# ---------------- Models ----------------
class BookCreate(BaseModel):
    title: str
    author: str = "Eccomi Online"
    language: str = "it"
    genre: str = "Saggio"
    description: Optional[str] = None

class BookOut(BaseModel):
    id: str
    title: str
    author: str
    language: str
    genre: str
    plan: str = "owner_full"
    chapters: List[Dict] = []

class ChapterCreate(BaseModel):
    title: str
    outline: Optional[str] = None
    prompt: Optional[str] = None

class ChapterOut(BaseModel):
    id: str
    title: str
    outline: Optional[str] = None
    prompt: Optional[str] = None
    text: Optional[str] = None

# --------------- Helpers ---------------
def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

def _is_owner(key: Optional[str]) -> bool:
    return key and key == OWNER_API_KEY

# --------------- Lifecycle ---------------
@app.on_event("startup")
def on_startup():
    print(f"✅ APP STARTED | ENV: {APP_ENV}")
    # (b) assicura cartelle scrivibili (in /tmp/eccomibook di default)
    storage.ensure_dirs()

# --------------- Default routes ---------------
@app.get("/", response_model=dict)
def root():
    return {"message": "EccomiBook Backend"}

@app.get("/health", response_model=dict)
def health():
    try:
        storage.ensure_dirs()
        ok = True
        note = "ok"
    except Exception as e:
        ok = False
        note = f"storage error: {e}"
    return {"status": "ok" if ok else "degraded", "env": APP_ENV, "service": APP_NAME, "storage": note}

# --------------- Books ---------------
@app.get("/books", response_model=List[BookOut])
def list_books():
    return list(BOOKS.values())

@app.post("/books", response_model=BookOut)
def create_book(
    body: BookCreate,
    x_api_key: Optional[str] = Header(default=None, convert_underscores=False)
):
    # Piano: owner_full se chiave coincide, altrimenti "growth" (limiti li attiveremo più avanti)
    plan = "owner_full" if _is_owner(x_api_key) else "growth"
    book_id = _new_id("book")
    BOOKS[book_id] = {
        "id": book_id,
        "title": body.title,
        "author": body.author,
        "language": body.language,
        "genre": body.genre,
        "description": body.description or "",
        "plan": plan,
        "chapters": [],
    }
    return BOOKS[book_id]

@app.post("/books/{book_id}/chapters", response_model=ChapterOut)
def add_chapter(
    book_id: str,
    body: ChapterCreate,
    x_api_key: Optional[str] = Header(default=None, convert_underscores=False)
):
    book = BOOKS.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    ch_id = _new_id("ch")
    chapter = {
        "id": ch_id,
        "title": body.title,
        "outline": (body.outline or ""),
        "prompt": (body.prompt or ""),
        "text": "",  # generazione testo a parte (/generate/chapter)
    }
    book["chapters"].append(chapter)
    return chapter

@app.put("/books/{book_id}/chapters/{chapter_id}", response_model=ChapterOut)
def update_chapter(
    book_id: str,
    chapter_id: str,
    body: ChapterCreate,
    x_api_key: Optional[str] = Header(default=None, convert_underscores=False)
):
    book = BOOKS.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    for ch in book["chapters"]:
        if ch["id"] == chapter_id:
            if body.title is not None:   ch["title"] = body.title
            if body.outline is not None: ch["outline"] = body.outline
            if body.prompt is not None:  ch["prompt"] = body.prompt
            return ch
    raise HTTPException(status_code=404, detail="Capitolo non trovato")

# --------------- Generate (MVP) ---------------
class GenChapterIn(BaseModel):
    title: str
    outline: Optional[str] = None
    prompt: Optional[str] = None
    book_id: Optional[str] = None

class GenChapterOut(BaseModel):
    id: str
    title: str
    outline: Optional[str] = None
    prompt: Optional[str] = None
    text: str

@app.post("/generate/chapter", response_model=GenChapterOut)
def generate_chapter(
    body: GenChapterIn,
    x_api_key: Optional[str] = Header(default=None, convert_underscores=False)
):
    # Stub di generazione “simil-AI”: crea un testo fittizio coerente
    base = body.prompt or body.outline or body.title
    generated = (
        f"{body.title}\n\n"
        f"{(body.outline or '').strip()}\n\n"
        f"Testo generato automaticamente a scopo demo. Prompt/outline: {base}"
    ).strip()

    ch_id = _new_id("ch")
    ch = {
        "id": ch_id,
        "title": body.title,
        "outline": body.outline or "",
        "prompt": body.prompt or "",
        "text": generated,
    }

    # se ci passa un book_id, aggiungiamo il capitolo al libro
    if body.book_id:
        book = BOOKS.get(body.book_id)
        if not book:
            raise HTTPException(status_code=404, detail="Libro non trovato")
        book["chapters"].append(ch)

    return ch

# --------------- Export ---------------
@app.get("/generate/export/book/{book_id}")
def export_book(
    book_id: str,
    format: str = Query("pdf", pattern="^(pdf|epub|docx)$"),
    x_api_key: Optional[str] = Header(default=None, convert_underscores=False),
):
    """
    Genera un export del libro (PDF/ePub/DOCX). Per ora implementiamo il PDF (MVP).
    Ritorna JSON con URL di download.
    """
    book = BOOKS.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    # Solo PDF implementato davvero nell’MVP; gli altri formati sono placeholder.
    ext = format.lower()
    if ext != "pdf":
        # placeholder finché non implementiamo gli altri
        _, filename = storage.exports_dir_and_filename(book_id, ext)
        url = f"/downloads/{filename}"  # non esisterà, ma manteniamo la forma
        return {
            "ok": True,
            "book_id": book_id,
            "format": ext,
            "file_name": filename,
            "url": url,
            "chapters": len(book["chapters"]),
            "generated_at": int(time.time()),
            "note": "Formato non ancora implementato; usa pdf."
        }

    # ---- PDF reale ----
    pdf_path = storage.export_pdf_path(book_id)
    storage.ensure_dirs()  # in caso la dir sia stata pulita da Render

    # Crea PDF semplice con titolo + capitoli
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4

    # Copertina
    c.setFont("Helvetica-Bold", 22)
    c.drawString(2 * cm, height - 3 * cm, book["title"])
    c.setFont("Helvetica", 12)
    c.drawString(2 * cm, height - 4 * cm, f"Autore: {book['author']}")
    c.drawString(2 * cm, height - 4.7 * cm, f"Genere: {book['genre']} • Lingua: {book['language']}")
    c.showPage()

    # Capitoli
    for idx, ch in enumerate(book["chapters"], start=1):
        c.setFont("Helvetica-Bold", 16)
        c.drawString(2 * cm, height - 2.5 * cm, f"Capitolo {idx}. {ch['title']}")
        c.setFont("Helvetica", 11)
        y = height - 3.5 * cm

        def draw_multiline(text: str, y_start: float) -> float:
            maxw = width - 4 * cm
            for line in text.split("\n"):
                # semplice wrap molto basico
                while line:
                    # rompi linee lunghe in blocchi ~100 char
                    chunk = line[:100]
                    c.drawString(2 * cm, y_start, chunk)
                    y_start -= 14
                    line = line[100:]
                    if y_start < 2 * cm:
                        c.showPage()
                        c.setFont("Helvetica", 11)
                        y_start = height - 2.5 * cm
            return y_start

        if ch.get("outline"):
            c.setFont("Helvetica-Oblique", 11)
            y = draw_multiline(f"Outline: {ch['outline']}", y)
            y -= 8

        c.setFont("Helvetica", 11)
        y = draw_multiline(ch.get("text") or "(Nessun testo generato)", y)

        c.showPage()

    c.save()

    filename = pdf_path.name
    url = f"/downloads/{filename}"
    return {
        "ok": True,
        "book_id": book_id,
        "format": "pdf",
        "file_name": filename,
        "url": url,
        "chapters": len(book["chapters"]),
        "generated_at": int(time.time()),
    }

# --------------- (c) Download dei file generati ---------------
@app.get("/downloads/{filename}")
def download_file(filename: str):
    """
    Restituisce un file dall'area di export (es: book_xxxxx.pdf).
    """
    path = (storage.EXPORTS_DIR / filename).resolve()

    # difesa minima: impedisci traversal
    if storage.EXPORTS_DIR not in path.parents and storage.EXPORTS_DIR != path.parent:
        raise HTTPException(status_code=400, detail="Filename non valido")

    if not path.exists():
        raise HTTPException(status_code=404, detail="File non trovato")

    return FileResponse(path, media_type="application/octet-stream", filename=filename)

# --------------- Pagina di test basic ---------------
@app.get("/test", response_class=HTMLResponse)
def test_page():
    return """
    <html><body style="font-family:system-ui;padding:24px">
      <h1>EccomiBook Backend</h1>
      <p>API online. Vai su <a href="/docs">/docs</a> per provare gli endpoint.</p>
    </body></html>
    """
