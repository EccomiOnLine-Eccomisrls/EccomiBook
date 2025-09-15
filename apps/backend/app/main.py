from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
from reportlab.pdfgen import canvas

app = FastAPI()

# --- memoria in RAM ---
books = {}

class BookCreate(BaseModel):
    title: str
    author: str
    language: str
    genre: str
    description: str

class ChapterCreate(BaseModel):
    title: str
    content: str

@app.post("/books")
def create_book(book: BookCreate):
    book_id = f"book_{len(books)+1}"
    books[book_id] = {"info": book.dict(), "chapters": []}
    return {"id": book_id, **book.dict()}

@app.post("/books/{book_id}/chapters")
def add_chapter(book_id: str, chapter: ChapterCreate):
    if book_id not in books:
        raise HTTPException(404, "Libro non trovato")
    ch_id = f"ch_{len(books[book_id]['chapters'])+1}"
    books[book_id]["chapters"].append({"id": ch_id, **chapter.dict()})
    return {"id": ch_id, **chapter.dict()}

@app.get("/generate/export/book/{book_id}")
def export_book(book_id: str, format: str = "pdf"):
    if book_id not in books:
        raise HTTPException(404, "Libro non trovato")

    # Percorso file
    file_name = f"{book_id}.pdf"
    file_path = f"/tmp/{file_name}"

    # Creazione PDF con reportlab
    c = canvas.Canvas(file_path)
    c.setFont("Helvetica", 16)
    c.drawString(100, 800, books[book_id]["info"]["title"])
    c.setFont("Helvetica", 12)

    y = 760
    for ch in books[book_id]["chapters"]:
        c.drawString(100, y, f"Capitolo: {ch['title']}")
        y -= 20
        c.drawString(120, y, ch["content"][:80] + "...")
        y -= 40
    c.save()

    # URL pubblico (endpoint sotto)
    url = f"https://eccomibook-backend.onrender.com/downloads/{file_name}"

    return {
        "ok": True,
        "book_id": book_id,
        "format": format,
        "file_name": file_name,
        "url": url,
        "chapters": len(books[book_id]["chapters"])
    }

@app.get("/downloads/{filename}")
def download_file(filename: str):
    file_path = f"/tmp/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(404, "File non trovato")
    return FileResponse(file_path, media_type="application/pdf", filename=filename)
