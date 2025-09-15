# apps/backend/app/main.py
from __future__ import annotations
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import os, io, datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

from . import storage

APP_NAME = os.getenv("APP_NAME", "EccomiBook Backend")
OWNER_API_KEY = os.getenv("OWNER_API_KEY", "")  # se presente → owner_full
STORAGE_DIR = os.getenv("STORAGE_DIR", "/data/eccomibook")

app = FastAPI(title=APP_NAME, version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# --------- MODELS ----------
class Plan(str):
    OWNER_FULL = "owner_full"
    START = "start"
    GROWTH = "growth"
    PRO = "pro"

class ChapterCreate(BaseModel):
    title: str = Field(..., description="Titolo capitolo")
    outline: Optional[str] = Field(None, description="Scaletta")
    prompt: Optional[str] = Field(None, description="Prompt/nota")

class ChapterOut(BaseModel):
    id: str
    title: str
    outline: Optional[str] = None
    prompt: Optional[str] = None
    content: Optional[str] = None  # placeholder per futuro generatore

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
    description: Optional[str] = None
    plan: str = Plan.OWNER_FULL
    chapters: List[ChapterOut] = []

# --------- HELPERS ----------
def get_state() -> Dict[str, Any]:
    return storage.load_state()

def save_state(s: Dict[str, Any]) -> None:
    storage.save_state(s)

def resolve_plan(request: Request) -> str:
    key = request.headers.get("x-api-key") or request.headers.get("X-Api-Key")
    if OWNER_API_KEY and key == OWNER_API_KEY:
        return Plan.OWNER_FULL
    return Plan.PRO  # default piano “buono” se non autenticato

def base_url(request: Request) -> str:
    url = str(request.base_url)  # termina con "/"
    return url

# --------- STARTUP ----------
@app.on_event("startup")
def on_startup():
    storage.ensure_dirs()
    _ = get_state()
    print(f"✅ Storage: {STORAGE_DIR}")

# --------- ROUTES ----------
@app.get("/")
def root():
    return {"message": APP_NAME}

@app.get("/health")
def health():
    s = get_state()
    return {
        "status": "ok",
        "service": APP_NAME,
        "env": os.getenv("APP_ENV", "production"),
        "books_count": len(s.get("books", {})),
        "storage_dir": STORAGE_DIR,
    }

@app.get("/books", response_model=List[BookOut])
def list_books():
    s = get_state()
    out: List[BookOut] = []
    for b in s["books"].values():
        out.append(BookOut(**b))
    return out

@app.post("/books", response_model=BookOut)
def create_book(body: BookCreate, request: Request):
    s = get_state()
    s["counters"]["books"] = int(s["counters"].get("books", 0)) + 1
    bid = storage.new_book_id(s["counters"]["books"])
    plan = resolve_plan(request)
    book = {
        "id": bid,
        "title": body.title,
        "author": body.author,
        "language": body.language,
        "genre": body.genre,
        "description": body.description,
        "plan": plan,
        "chapters": [],
    }
    s["books"][bid] = book
    save_state(s)
    return BookOut(**book)

@app.post("/books/{book_id}/chapters", response_model=ChapterOut)
def add_chapter(book_id: str, body: ChapterCreate):
    s = get_state()
    book = s["books"].get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    s["counters"]["chapters"] = int(s["counters"].get("chapters", 0)) + 1
    cid = storage.new_chapter_id(s["counters"]["chapters"])
    ch = {
        "id": cid,
        "title": body.title,
        "outline": body.outline,
        "prompt": body.prompt,
        "content": None,
    }
    book["chapters"].append(ch)
    save_state(s)
    return ChapterOut(**ch)

@app.put("/books/{book_id}/chapters/{chapter_id}", response_model=ChapterOut)
def update_chapter(book_id: str, chapter_id: str, body: ChapterCreate):
    s = get_state()
    book = s["books"].get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    for ch in book["chapters"]:
        if ch["id"] == chapter_id:
            ch["title"] = body.title
            ch["outline"] = body.outline
            ch["prompt"] = body.prompt
            save_state(s)
            return ChapterOut(**ch)
    raise HTTPException(status_code=404, detail="Capitolo non trovato")

# ------- GENERAZIONE (placeholder) -------
class GenReq(BaseModel):
    topic: str
    style: Optional[str] = None

@app.post("/generate/chapter", response_model=ChapterOut)
def generate_chapter(body: GenReq, book_id: Optional[str] = None, request: Request = None):
    # Placeholder: crea un capitolo “vuoto” con content fake
    ch = ChapterCreate(
        title=body.topic,
        outline=f"Scaletta: {body.topic}",
        prompt=f"Stile: {body.style or 'standard'}"
    )
    created = add_chapter(book_id, ch) if book_id else ChapterOut(
        id=storage.new_chapter_id(), title=ch.title, outline=ch.outline, prompt=ch.prompt, content=None
    )
    return created

# ------- EXPORT -------
@app.get("/generate/export/book/{book_id}")
def export_book(book_id: str, format: str = Query("pdf", pattern="^(pdf|epub|docx)$"), request: Request = None):
    s = get_state()
    book = s["books"].get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    if format != "pdf":
        # implementeremo ePub/DOCX più avanti
        raise HTTPException(status_code=501, detail="Solo PDF supportato in questa versione")

    # Crea PDF
    filename = f"{book_id}.pdf"
    export_dir = storage.exports_dir()
    os.makedirs(export_dir, exist_ok=True)
    pdf_path = os.path.join(export_dir, filename)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4

    # Copertina semplice
    c.setFont("Helvetica-Bold", 20)
    c.drawString(2*cm, h-3*cm, book["title"])
    c.setFont("Helvetica", 12)
    c.drawString(2*cm, h-4*cm, f"Autore: {book['author']}")
    c.drawString(2*cm, h-4.7*cm, f"Lingua: {book['language']}  •  Genere: {book['genre']}")
    if book.get("description"):
        text = c.beginText(2*cm, h-6*cm)
        text.setFont("Helvetica", 11)
        for line in break_lines(book["description"], max_chars=90):
            text.textLine(line)
        c.drawText(text)
    c.showPage()

    # Capitoli
    for i, ch in enumerate(book["chapters"], 1):
        c.setFont("Helvetica-Bold", 16)
        c.drawString(2*cm, h-3*cm, f"Capitolo {i}: {ch.get('title','')}")
        c.setFont("Helvetica", 11)
        y = h-4.5*cm
        for label in ("outline", "prompt", "content"):
            val = ch.get(label)
            if val:
                y = draw_paragraph(c, f"{label.capitalize()}:", val, 2*cm, y, w-4*cm)
                y -= 0.5*cm
        c.showPage()

    c.save()
    with open(pdf_path, "wb") as f:
        f.write(buffer.getvalue())

    # URL pubblico per il download
    base = base_url(request).rstrip("/")
    url = f"{base}/downloads/{filename}"

    return {
        "ok": True,
        "book_id": book_id,
        "format": format,
        "file_name": filename,
        "url": url,
        "chapters": len(book["chapters"]),
        "generated_at": int(datetime.datetime.utcnow().timestamp()),
    }

def break_lines(text: str, max_chars: int = 90):
    words = (text or "").split()
    line, out = [], []
    for w in words:
        if sum(len(x) for x in line) + len(line) + len(w) > max_chars:
            out.append(" ".join(line)); line = [w]
        else:
            line.append(w)
    if line: out.append(" ".join(line))
    return out

def draw_paragraph(c: canvas.Canvas, title: str, body: str, x: float, y: float, max_w: float) -> float:
    c.setFont("Helvetica-Bold", 12); c.drawString(x, y, title); y -= 0.4*cm
    c.setFont("Helvetica", 11)
    for line in break_lines(body, max_chars=100):
        c.drawString(x, y, line)
        y -= 0.4*cm
        if y < 3*cm:
            c.showPage(); y = A4[1]-3*cm
            c.setFont("Helvetica", 11)
    return y

# --------- FILE DOWNLOAD ----------
@app.get("/downloads/{filename}")
def download_file(filename: str):
    path = os.path.join(storage.exports_dir(), filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File non trovato")
    return FileResponse(path, filename=filename, media_type="application/pdf")
