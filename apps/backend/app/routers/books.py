from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import FileResponse
from typing import List
from app import storage
from app.models import (
    Book, Chapter, BookList,
    CreateBookReq, GenerateOutlineReq,
    GenerateChapterReq, EditChapterReq, ExportReq
)
from app import ai

router = APIRouter()

# ---------- BOOKS ----------
@router.get("/books", response_model=BookList)
def list_books():
    return BookList(items=storage.list_books())

@router.post("/books", response_model=Book)
def create_book(body: CreateBookReq):
    b = storage.create_book(body.title, body.genre, body.language, body.plan)
    return b

@router.get("/books/{book_id}", response_model=Book)
def get_book(book_id: str = Path(...)):
    b = storage.get_book(book_id)
    if not b:
        raise HTTPException(status_code=404, detail="book not found")
    return b

@router.post("/books/{book_id}/outline", response_model=Book)
def generate_outline(book_id: str, body: GenerateOutlineReq):
    b = storage.get_book(book_id)
    if not b: raise HTTPException(status_code=404, detail="book not found")
    b.outline = ai.generate_outline(b.title, body.chapters, b.language)
    storage.save_book(b)
    return b

# ---------- CHAPTERS ----------
@router.get("/books/{book_id}/chapters", response_model=List[Chapter])
def list_chapters(book_id: str):
    b = storage.get_book(book_id)
    if not b: raise HTTPException(status_code=404, detail="book not found")
    return b.chapters

@router.post("/books/{book_id}/chapters", response_model=Chapter)
def add_chapter(book_id: str, body: GenerateChapterReq):
    b = storage.get_book(book_id)
    if not b: raise HTTPException(status_code=404, detail="book not found")

    # titolo default: outline[chapter_index] se presente
    title = None
    if 0 <= body.chapter_index < len(b.outline):
        title = b.outline[body.chapter_index]
    if not title:
        title = f"Capitolo {body.chapter_index + 1}"

    md = ai.generate_chapter_md(title, body.prompt, b.language)
    imgs = ai.generate_image_urls(body.images, body.hd_images)

    ch = storage.add_chapter(book_id, title, md, imgs)
    return ch

@router.patch("/books/{book_id}/chapters/{chapter_id}", response_model=Chapter)
def edit_chapter(book_id: str, chapter_id: str, body: EditChapterReq):
    ch = storage.update_chapter(book_id, chapter_id, body.title, body.content_md)
    return ch

# ---------- EXPORT ----------
@router.post("/books/{book_id}/export")
def export_book(book_id: str, body: ExportReq):
    b = storage.get_book(book_id)
    if not b: raise HTTPException(status_code=404, detail="book not found")

    if body.fmt == "json":
        path = storage.export_book_json(b)
        media = "application/json"
        filename = f"{b.id}.json"
    else:
        path = storage.export_book_mdzip(b)
        media = "application/zip"
        filename = f"{b.id}.zip"

    return FileResponse(path, media_type=media, filename=filename)
