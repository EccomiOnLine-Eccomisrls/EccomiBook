# app/models.py
from typing import List, Optional
from pydantic import BaseModel
from enum import Enum


# ----- Piani -----
class Plan(str, Enum):
    OWNER_FULL = "owner_full"
    START = "start"
    GROWTH = "growth"
    PRO = "pro"


PLAN_CAPS = {
    Plan.OWNER_FULL: dict(max_books=None, max_chapters_per_day=None, images_hd=True, export_hd=True, priority="highest"),
    Plan.START:      dict(max_books=1,   max_chapters_per_day=10,  images_hd=False, export_hd=True,  priority="normal"),
    Plan.GROWTH:     dict(max_books=5,   max_chapters_per_day=50,  images_hd=True,  export_hd=True,  priority="high"),
    Plan.PRO:        dict(max_books=None,max_chapters_per_day=200, images_hd=True,  export_hd=True,  priority="max"),
}


# ----- DTO -----
class BookCreate(BaseModel):
    title: str
    language: str = "it"
    genre: str = "general"
    plan: Plan = Plan.START


class ChapterCreate(BaseModel):
    title: str
    prompt: str
    order: int | None = None


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class GenerateChapterIn(BaseModel):
    book_id: str
    prompt: str
    images: int = 0  # quante immagini generare (placeholder per ora)


class ChapterOut(BaseModel):
    id: str
    title: str
    order: int
    content: str
    images: List[str] = []


class BookOut(BaseModel):
    id: str
    title: str
    language: str
    genre: str
    plan: Plan
    chapters: List[ChapterOut] = []
