# app/routers/books.py
from fastapi import APIRouter, HTTPException, Depends, Response
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from ..models import Book, Chapter, CreateBookInput, GenerateChapterInput, ExportFormat, PLAN_CAPS
from ..storage import store, new_id
from ..routers.auth import get_current_user, UserCtx
from ..ai import generate_chapter

router = APIRouter(prefix="/api", tags=["EccomiBook"])

@router.get("/caps")
def caps(user: UserCtx = Depends(get_current_user)):
    return PLAN_CAPS[user.plan]

@router.get("/books")
def list_books(user: UserCtx = Depends(get_current_user)):
    return store.list_books()

@router.post("/books", response_model=Book)
def create_book(body: CreateBookInput, user: UserCtx = Depends(get_current_user)):
    caps = PLAN_CAPS[user.plan]
    if caps["max_books"] is not None and len(store.list_books()) >= caps["max_books"]:
        raise HTTPException(status_code=403, detail="Limite libri raggiunto per il tuo piano.")
    b = Book(id=new_id("bk"), title=body.title, synopsis=body.synopsis, genre=body.genre, language=body.language, plan=user.plan)
    return store.create_book(b)

@router.get("/books/{book_id}", response_model=Book)
def get_book(book_id: str, user: UserCtx = Depends(get_current_user)):
    b = store.get_book(book_id)
    if not b: raise HTTPException(404, "Book not found")
    return b

@router.delete("/books/{book_id}")
def delete_book(book_id: str, user: UserCtx = Depends(get_current_user)):
    ok = store.delete_book(book_id)
    if not ok: raise HTTPException(404, "Book not found")
    return {"ok": True}

@router.post("/books/{book_id}/chapters", response_model=Chapter)
def add_chapter(book_id: str, body: GenerateChapterInput, user: UserCtx = Depends(get_current_user)):
    b = store.get_book(book_id)
    if not b: raise HTTPException(404, "Book not found")
    ch = generate_chapter(body.title_hint, body.words, body.want_image and PLAN_CAPS[user.plan]["images_hd"])
    return store.add_chapter(book_id, ch)

@router.get("/books/{book_id}/export")
def export_zip(book_id: str, fmt: ExportFormat = ExportFormat.ZIP_MARKDOWN, user: UserCtx = Depends(get_current_user)):
    b = store.get_book(book_id)
    if not b: raise HTTPException(404, "Book not found")
    buf = BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as z:
        z.writestr("README.txt", f"Titolo: {b.title}\nLingua: {b.language}\nCapitoli: {len(b.chapters)}")
        for i, ch in enumerate(b.chapters, 1):
            z.writestr(f"chapters/{i:02d}_{ch.title.replace(' ', '_')}.md", f"# {ch.title}\n\n{ch.text}\n")
    buf.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="{b.title.replace(" ", "_")}.zip"'}
    return Response(content=buf.read(), media_type="application/zip", headers=headers)
