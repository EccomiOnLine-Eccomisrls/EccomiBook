# app/routers/books.py
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List
from app.models import BookCreate, BookOut, ChapterCreate, ChapterUpdate, ChapterOut, PLAN_CAPS, Plan
from app.storage import DB, new_id

router = APIRouter(prefix="/books", tags=["Books"])

# ---- auth/plan minimal ----
def get_plan(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> Plan:
    # Semplice: se manca API key, consideriamo START (per demo).
    # Il vero controllo piani lo collegheremo a Shopify.
    if x_api_key and x_api_key.startswith("owner_"):
        return Plan.OWNER_FULL
    return Plan.START


@router.get("", response_model=List[BookOut])
def list_books():
    return list(DB["books"].values())


@router.post("", response_model=BookOut)
def create_book(body: BookCreate, plan: Plan = Depends(get_plan)):
    caps = PLAN_CAPS[plan]
    if caps["max_books"] is not None and len(DB["books"]) >= caps["max_books"]:
        raise HTTPException(status_code=403, detail="Limite libri raggiunto per il tuo piano")

    book_id = new_id("book")
    DB["books"][book_id] = {
        "id": book_id,
        "title": body.title,
        "language": body.language,
        "genre": body.genre,
        "plan": body.plan,
        "chapters": [],
        "created_at": None,
    }
    return DB["books"][book_id]


@router.post("/{book_id}/chapters", response_model=ChapterOut)
def add_chapter(book_id: str, body: ChapterCreate, plan: Plan = Depends(get_plan)):
    book = DB["books"].get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")

    order = body.order if body.order is not None else len(book["chapters"]) + 1
    chap_id = new_id("ch")
    chapter = {
        "id": chap_id,
        "title": body.title,
        "order": int(order),
        "content": f"(Bozza) {body.prompt}",
        "images": [],
    }
    DB["chapters"][chap_id] = chapter
    book["chapters"].append(chapter)
    return chapter


@router.put("/{book_id}/chapters/{chapter_id}", response_model=ChapterOut)
def update_chapter(book_id: str, chapter_id: str, body: ChapterUpdate):
    book = DB["books"].get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro non trovato")
    chapter = DB["chapters"].get(chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Capitolo non trovato")

    if body.title is not None:
        chapter["title"] = body.title
    if body.content is not None:
        chapter["content"] = body.content
    return chapter
